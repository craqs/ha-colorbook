"""Minimal IPP client for submitting a Print-Job to a network printer.

We construct IPP requests by hand (RFC 8010/8011) to avoid heavy dependencies.

Status 0x0406 = client-error-not-found: the printer-uri in the request does
not match any queue the server knows about. Use `python -m app.printer --discover`
to list available queues from the CUPS server.
"""

from __future__ import annotations

import http.client
import logging
import socket
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from .config import SETTINGS
from .pdf import png_to_pdf

log = logging.getLogger(__name__)

# Auto-discovered queue path cached for the lifetime of the process.
# None  → not yet resolved
# str   → resolved (may have come from config or from discovery)
_resolved_queue: str | None = None


def _auto_discover_queue() -> str:
    """Run CUPS-Get-Printers and return the first available queue path."""
    log.info("Auto-discovering printer queue on %s:%s …",
             SETTINGS.printer_host, SETTINGS.printer_port)
    printers = discover_printers()
    if not printers:
        raise RuntimeError(
            "Nie znaleziono żadnych drukarek na serwerze "
            f"{SETTINGS.printer_host}:{SETTINGS.printer_port}."
        )
    for p in printers:
        paths = p.queue_paths
        if paths:
            queue = paths[0].lstrip("/")
            log.info("Auto-discovered queue: %s  (printer: %s)", queue, p.name)
            return queue
    raise RuntimeError("Serwer CUPS odpowiedział, ale nie zwrócił ścieżek kolejek.")


def _get_queue() -> str:
    """Return the queue to use, running discovery if necessary."""
    global _resolved_queue
    if _resolved_queue is not None:
        return _resolved_queue
    configured = SETTINGS.printer_queue.strip().lstrip("/")
    if configured:
        # Trust the configured value; we'll fall back to discovery on 0x0406.
        _resolved_queue = configured
    else:
        _resolved_queue = _auto_discover_queue()
    return _resolved_queue


def invalidate_queue_cache() -> None:
    """Force re-discovery on the next print (call after changing config)."""
    global _resolved_queue
    _resolved_queue = None

# ---------------------------------------------------------------------------
# IPP constants
# ---------------------------------------------------------------------------

_IPP_VERSION = b"\x02\x00"
_OP_PRINT_JOB           = 0x0002
_OP_GET_PRINTER_ATTRS   = 0x000B
_OP_CUPS_GET_PRINTERS   = 0x4002   # CUPS extension

_STATUS_OK          = 0x0000
_STATUS_OK_IGNORED  = 0x0001

# Delimiter tags
_TAG_OPERATION_ATTRIBUTES = 0x01
_TAG_JOB_ATTRIBUTES       = 0x02
_TAG_END_OF_ATTRIBUTES    = 0x03
_TAG_PRINTER_ATTRIBUTES   = 0x04

# Value tags
_TAG_INTEGER            = 0x21
_TAG_BOOLEAN            = 0x22
_TAG_ENUM               = 0x23
_TAG_KEYWORD            = 0x44
_TAG_URI                = 0x45
_TAG_NAME_WITHOUT_LANG  = 0x42
_TAG_TEXT_WITHOUT_LANG  = 0x41
_TAG_CHARSET            = 0x47
_TAG_NATURAL_LANGUAGE   = 0x48
_TAG_MIME_MEDIA_TYPE    = 0x49

_STATUS_NAMES = {
    0x0000: "successful-ok",
    0x0001: "successful-ok-ignored-or-substituted-attributes",
    0x0400: "client-error-bad-request",
    0x0401: "client-error-forbidden",
    0x0402: "client-error-not-authenticated",
    0x0403: "client-error-not-authorized",
    0x0404: "client-error-not-possible",
    0x0405: "client-error-timeout",
    0x0406: "client-error-not-found",           # ← wrong URI / queue
    0x0407: "client-error-gone",
    0x0408: "client-error-request-entity-too-large",
    0x0409: "client-error-request-value-too-long",
    0x040A: "client-error-document-format-not-supported",
    0x040B: "client-error-attributes-or-values-not-supported",
    0x040C: "client-error-uri-scheme-not-supported",
    0x040D: "client-error-charset-not-supported",
    0x0500: "server-error-internal-error",
    0x0501: "server-error-operation-not-supported",
    0x0503: "server-error-service-unavailable",
    0x0504: "server-error-version-not-supported",
    0x0507: "server-error-printer-is-deactivated",
}

# ---------------------------------------------------------------------------
# Encoding helpers
# ---------------------------------------------------------------------------

def _attr(tag: int, name: bytes, value: bytes) -> bytes:
    return (
        struct.pack("!B", tag)
        + struct.pack("!H", len(name)) + name
        + struct.pack("!H", len(value)) + value
    )


def _op_header(operation: int, request_id: int = 1) -> bytes:
    return _IPP_VERSION + struct.pack("!H", operation) + struct.pack("!I", request_id)


def _base_op_attrs(printer_uri: str | None = None) -> bytes:
    """Minimal mandatory operation attributes."""
    data = struct.pack("!B", _TAG_OPERATION_ATTRIBUTES)
    data += _attr(_TAG_CHARSET,          b"attributes-charset",          b"utf-8")
    data += _attr(_TAG_NATURAL_LANGUAGE, b"attributes-natural-language", b"en-us")
    if printer_uri:
        data += _attr(_TAG_URI, b"printer-uri", printer_uri.encode())
    return data


def _build_print_job(
    printer_uri: str,
    document: bytes,
    job_name: str,
    mime_type: str = "application/pdf",
    user: str = "colorbook",
    request_id: int = 1,
) -> bytes:
    header = _op_header(_OP_PRINT_JOB, request_id)
    ops = _base_op_attrs(printer_uri)
    ops += _attr(_TAG_NAME_WITHOUT_LANG, b"requesting-user-name", user.encode())
    ops += _attr(_TAG_NAME_WITHOUT_LANG, b"job-name", job_name.encode())
    ops += _attr(_TAG_MIME_MEDIA_TYPE,   b"document-format", mime_type.encode("ascii"))
    return header + ops + struct.pack("!B", _TAG_END_OF_ATTRIBUTES) + document


def _build_get_printer_attrs(printer_uri: str, request_id: int = 1) -> bytes:
    header = _op_header(_OP_GET_PRINTER_ATTRS, request_id)
    ops = _base_op_attrs(printer_uri)
    ops += _attr(_TAG_NAME_WITHOUT_LANG, b"requesting-user-name", b"colorbook")
    for attr_name in (b"printer-uri-supported", b"printer-name",
                      b"document-format-supported", b"printer-state"):
        ops += _attr(_TAG_KEYWORD, b"requested-attributes", attr_name)
    return header + ops + struct.pack("!B", _TAG_END_OF_ATTRIBUTES)


def _build_cups_get_printers(request_id: int = 1) -> bytes:
    header = _op_header(_OP_CUPS_GET_PRINTERS, request_id)
    ops = _base_op_attrs()
    ops += _attr(_TAG_NAME_WITHOUT_LANG, b"requesting-user-name", b"colorbook")
    for attr_name in (b"printer-uri-supported", b"printer-name",
                      b"device-uri", b"printer-info", b"printer-state"):
        ops += _attr(_TAG_KEYWORD, b"requested-attributes", attr_name)
    return header + ops + struct.pack("!B", _TAG_END_OF_ATTRIBUTES)

# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _walk_attrs(body: bytes) -> Iterator[tuple[int, int, bytes, bytes]]:
    """Yield (group_tag, value_tag, name, value) from an IPP response body.

    Skips the 8-byte header (version + status-code + request-id).
    For multi-value attributes (empty name), re-emits the previous name.
    """
    pos = 8
    current_group = 0
    current_name = b""
    while pos < len(body):
        tag = body[pos]; pos += 1
        if tag == _TAG_END_OF_ATTRIBUTES:
            break
        if tag <= 0x0F:          # delimiter tag
            current_group = tag
            current_name = b""
            continue
        if pos + 2 > len(body):
            break
        name_len = struct.unpack("!H", body[pos:pos + 2])[0]; pos += 2
        name = body[pos:pos + name_len]; pos += name_len
        if pos + 2 > len(body):
            break
        val_len = struct.unpack("!H", body[pos:pos + 2])[0]; pos += 2
        value = body[pos:pos + val_len]; pos += val_len
        if name:
            current_name = name
        else:
            name = current_name         # continuation / multi-value
        yield current_group, tag, name, value


def _parse_print_response(body: bytes) -> tuple[int, int | None]:
    """Return (ipp_status_code, job_id)."""
    if len(body) < 8:
        raise RuntimeError("IPP response too short.")
    status = struct.unpack("!H", body[2:4])[0]
    job_id: int | None = None
    for _, vtag, name, value in _walk_attrs(body):
        if name == b"job-id" and vtag == _TAG_INTEGER and len(value) == 4:
            job_id = struct.unpack("!i", value)[0]
            break
    return status, job_id


@dataclass
class PrinterInfo:
    name: str = ""
    uris: list[str] = field(default_factory=list)
    formats: list[str] = field(default_factory=list)
    state: int | None = None

    @property
    def queue_paths(self) -> list[str]:
        """Return URL paths inferred from URIs (e.g. '/printers/Brother')."""
        paths = []
        for uri in self.uris:
            # ipp://host:631/printers/Name  →  /printers/Name
            for scheme in ("ipp://", "ipps://"):
                if uri.startswith(scheme):
                    rest = uri[len(scheme):]
                    slash = rest.find("/")
                    if slash != -1:
                        paths.append(rest[slash:])
        return paths


def _parse_printer_list(body: bytes) -> list[PrinterInfo]:
    printers: list[PrinterInfo] = []
    current: PrinterInfo | None = None
    for group, vtag, name, value in _walk_attrs(body):
        if group != _TAG_PRINTER_ATTRIBUTES:
            continue
        # A new printer block starts when we see printer-name or
        # printer-uri-supported with a non-empty name.
        text = value.decode("utf-8", errors="replace")
        if name == b"printer-name":
            if current is None or current.name:   # start a new printer block
                if current is not None:
                    printers.append(current)
                current = PrinterInfo()
            current.name = text
        else:
            if current is None:
                current = PrinterInfo()
            if name == b"printer-uri-supported" and vtag == _TAG_URI:
                current.uris.append(text)
            elif name == b"document-format-supported" and vtag == _TAG_MIME_MEDIA_TYPE:
                current.formats.append(text)
            elif name == b"printer-state" and vtag == _TAG_ENUM and len(value) == 4:
                current.state = struct.unpack("!i", value)[0]
    if current is not None:
        printers.append(current)
    return printers

# ---------------------------------------------------------------------------
# HTTP transport
# ---------------------------------------------------------------------------

def _ipp_post(host: str, port: int, path: str, body: bytes, timeout: int = 30) -> bytes:
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request("POST", path, body=body, headers={
            "Content-Type": "application/ipp",
            "Content-Length": str(len(body)),
        })
        resp = conn.getresponse()
        return resp.read()
    except (socket.gaierror, OSError) as exc:
        raise RuntimeError(f"Cannot connect to {host}:{port}: {exc}") from exc
    finally:
        conn.close()

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class PrintResult:
    ok: bool
    status_code: int
    status_name: str
    job_id: int | None
    raw_http_status: int = 200


def discover_printers() -> list[PrinterInfo]:
    """Ask the CUPS server (CUPS-Get-Printers) for all configured queues."""
    host, port = SETTINGS.printer_host, SETTINGS.printer_port
    if not host:
        raise RuntimeError("printer_host is not set.")
    body = _build_cups_get_printers()
    raw = _ipp_post(host, port, "/", body)
    return _parse_printer_list(raw)


def get_printer_attributes(queue: str | None = None) -> PrinterInfo:
    """Get attributes for the configured (or given) queue."""
    host, port = SETTINGS.printer_host, SETTINGS.printer_port
    q = (queue or SETTINGS.printer_queue).lstrip("/")
    uri = f"ipp://{host}:{port}/{q}"
    body = _build_get_printer_attrs(uri)
    raw = _ipp_post(host, port, f"/{q}", body)
    infos = _parse_printer_list(raw)
    if infos:
        return infos[0]
    return PrinterInfo(uris=[uri])


def print_png_file(png_path: Path | str, job_name: str = "Kolorowanka") -> PrintResult:
    png_path = Path(png_path)
    pdf_bytes = png_to_pdf(png_path.read_bytes(), SETTINGS.paper_size)  # type: ignore[arg-type]
    return submit_pdf(pdf_bytes, job_name=job_name)


def _do_submit(host: str, port: int, queue: str,
               pdf_bytes: bytes, job_name: str) -> tuple[int, int | None, int]:
    """Low-level send; returns (ipp_status, job_id, http_status)."""
    printer_uri = f"ipp://{host}:{port}/{queue}"
    log.info("IPP Print-Job → %s  (pdf=%d B)", printer_uri, len(pdf_bytes))
    body = _build_print_job(printer_uri=printer_uri, document=pdf_bytes, job_name=job_name)
    conn = http.client.HTTPConnection(host, port, timeout=60)
    try:
        conn.request("POST", f"/{queue}", body=body, headers={
            "Content-Type": "application/ipp",
            "Content-Length": str(len(body)),
        })
        resp = conn.getresponse()
        http_status = resp.status
        resp_body = resp.read()
    except (socket.gaierror, OSError) as exc:
        raise RuntimeError(
            f"Nie można połączyć się z drukarką {host}:{port}: {exc}"
        ) from exc
    finally:
        conn.close()
    if http_status >= 400:
        raise RuntimeError(f"Drukarka odrzuciła żądanie HTTP {http_status}.")
    status, job_id = _parse_print_response(resp_body)
    return status, job_id, http_status


def submit_pdf(pdf_bytes: bytes, job_name: str = "Kolorowanka") -> PrintResult:
    global _resolved_queue
    host, port = SETTINGS.printer_host, SETTINGS.printer_port

    if not host:
        raise RuntimeError("Nie ustawiono adresu drukarki (printer_host).")

    queue = _get_queue()
    status, job_id, http_status = _do_submit(host, port, queue, pdf_bytes, job_name)

    # 0x0406 = client-error-not-found: queue path is wrong.
    # Clear the cache and try once more with fresh auto-discovery.
    if status == 0x0406:
        log.warning("Queue '%s' not found — running auto-discovery and retrying.", queue)
        _resolved_queue = None          # force fresh discovery
        invalidate_queue_cache()
        queue = _auto_discover_queue()
        _resolved_queue = queue
        status, job_id, http_status = _do_submit(host, port, queue, pdf_bytes, job_name)

    ok = status in (_STATUS_OK, _STATUS_OK_IGNORED)
    status_name = _STATUS_NAMES.get(status, f"ipp-status-0x{status:04x}")
    if not ok:
        raise RuntimeError(f"Drukarka zwróciła błąd IPP: {status_name}")
    return PrintResult(ok=ok, status_code=status, status_name=status_name,
                       job_id=job_id, raw_http_status=http_status)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    import os
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    args = sys.argv[1:]

    if not args or args[0] == "--help":
        print("Usage:")
        print("  python -m app.printer --discover          list CUPS queues")
        print("  python -m app.printer --info [queue]      get printer attributes")
        print("  python -m app.printer <path-to.png>       submit test print job")
        sys.exit(0)

    if args[0] == "--discover":
        printers = discover_printers()
        if not printers:
            print("No printers found (empty CUPS-Get-Printers response).")
        for p in printers:
            state_map = {3: "idle", 4: "processing", 5: "stopped"}
            state_str = state_map.get(p.state, str(p.state)) if p.state else "?"
            print(f"\nPrinter: {p.name}  state={state_str}")
            for uri in p.uris:
                print(f"  URI: {uri}")
            for path in p.queue_paths:
                print(f"  → set printer_queue = {path.lstrip('/')}")
            if p.formats:
                print(f"  Formats: {', '.join(p.formats)}")
        sys.exit(0)

    if args[0] == "--info":
        queue = args[1] if len(args) > 1 else None
        info = get_printer_attributes(queue)
        print(f"Name: {info.name}")
        for uri in info.uris:
            print(f"  URI: {uri}")
        for fmt in info.formats:
            print(f"  Format: {fmt}")
        sys.exit(0)

    result = print_png_file(args[0])
    print(f"OK  job_id={result.job_id}  status={result.status_name}")
