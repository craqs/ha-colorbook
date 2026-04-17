"""Flask application exposing the Colorbook UI and JSON API."""

from __future__ import annotations

import logging
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from . import history, openai_client
from .config import SETTINGS
from .printer import submit_pdf, discover_printers
from .pdf import png_to_pdf
from .prompt import build_prompt

log = logging.getLogger(__name__)


class IngressPrefixMiddleware:
    """Honor Home Assistant ingress by exposing its prefix as SCRIPT_NAME.

    HA strips the ingress prefix from PATH_INFO before forwarding, and passes
    the public prefix in ``X-Ingress-Path``. Setting SCRIPT_NAME makes
    Flask's ``url_for`` emit URLs that include the prefix, so image <img
    src> and any other absolute paths resolve correctly in the browser.
    """

    def __init__(self, wsgi_app):
        self._wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        prefix = environ.get("HTTP_X_INGRESS_PATH", "")
        if prefix:
            environ["SCRIPT_NAME"] = prefix.rstrip("/")
        return self._wsgi_app(environ, start_response)


def create_app() -> Flask:
    logging.basicConfig(level=logging.INFO)
    app = Flask(__name__, template_folder="templates", static_folder="static")
    # HA ingress prefix → SCRIPT_NAME (outer), then ProxyFix for other headers.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)  # type: ignore[assignment]
    app.wsgi_app = IngressPrefixMiddleware(app.wsgi_app)  # type: ignore[assignment]

    history.init()

    # --- UI ----------------------------------------------------------------

    @app.get("/")
    def index():
        return render_template(
            "index.html",
            auto_accept_default=SETTINGS.auto_accept_default,
            paper_size=SETTINGS.paper_size,
            language=SETTINGS.language,
        )

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.get("/api/config")
    def api_config():
        return jsonify({
            "auto_accept_default": SETTINGS.auto_accept_default,
            "paper_size": SETTINGS.paper_size,
            "image_model": SETTINGS.openai_image_model,
            "language": SETTINGS.language,
        })

    @app.get("/api/printer-discover")
    def api_printer_discover():
        """Return CUPS queue list — useful for figuring out the right printer_queue value."""
        try:
            printers = discover_printers()
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 502
        result = []
        for p in printers:
            result.append({
                "name": p.name,
                "uris": p.uris,
                "queue_paths": p.queue_paths,
                "formats": p.formats,
                "state": p.state,
            })
        return jsonify({"printers": result})

    # --- Generation --------------------------------------------------------

    @app.post("/api/generate")
    def api_generate():
        data = request.get_json(silent=True) or {}
        topic = (data.get("topic") or "").strip()
        refinement = (data.get("refinement") or "").strip() or None
        parent_id = (data.get("parent_id") or "").strip() or None

        if not topic:
            return jsonify({"error": "Please enter a topic."}), 400

        try:
            full_prompt = build_prompt(topic, refinement)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        try:
            png_bytes = openai_client.generate_image(full_prompt)
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 500
        except Exception as exc:
            log.exception("Image generation failed")
            return jsonify({"error": f"Image generation failed: {exc}"}), 502

        item = history.save_generation(
            topic=topic,
            full_prompt=full_prompt,
            refinement=refinement,
            parent_id=parent_id,
            model=SETTINGS.openai_image_model,
            png_bytes=png_bytes,
        )
        payload = item.to_dict()
        payload["image_url"] = url_for("api_history_image", item_id=item.id)
        return jsonify(payload)

    @app.get("/api/random-topic")
    def api_random_topic():
        try:
            topic = openai_client.random_topic(language=SETTINGS.language)
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 500
        except Exception as exc:
            log.exception("Random topic failed")
            return jsonify({"error": f"Failed to generate random topic: {exc}"}), 502
        return jsonify({"topic": topic})

    # --- Printing ----------------------------------------------------------

    @app.post("/api/print")
    def api_print():
        data = request.get_json(silent=True) or {}
        item_id = (data.get("id") or "").strip()
        if not item_id:
            return jsonify({"error": "Missing image ID."}), 400
        item = history.get(item_id)
        if item is None:
            return jsonify({"error": "Image not found in history."}), 404

        png_path: Path = history.image_path(item)
        if not png_path.exists():
            return jsonify({"error": "Image file is missing from disk."}), 410

        try:
            pdf_bytes = png_to_pdf(png_path.read_bytes(), SETTINGS.paper_size)  # type: ignore[arg-type]
            result = submit_pdf(pdf_bytes, job_name=f"Colorbook: {item.topic}")
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 502
        except Exception as exc:
            log.exception("Print failed")
            return jsonify({"error": f"Print failed: {exc}"}), 502

        history.mark_printed(item.id)
        return jsonify({
            "ok": True,
            "job_id": result.job_id,
            "status": result.status_name,
        })

    # --- History -----------------------------------------------------------

    @app.get("/api/history")
    def api_history():
        try:
            limit = int(request.args.get("limit", 50))
            offset = int(request.args.get("offset", 0))
        except ValueError:
            return jsonify({"error": "limit/offset must be integers."}), 400
        items = history.list_items(limit=limit, offset=offset)
        payload = []
        for item in items:
            d = item.to_dict()
            d["image_url"] = url_for("api_history_image", item_id=item.id)
            payload.append(d)
        return jsonify({"items": payload})

    @app.get("/api/history/<item_id>/image")
    def api_history_image(item_id: str):
        item = history.get(item_id)
        if item is None:
            abort(404)
        path = history.image_path(item)
        if not path.exists():
            abort(404)
        return send_file(path, mimetype="image/png", max_age=3600)

    @app.delete("/api/history/<item_id>")
    def api_history_delete(item_id: str):
        ok = history.delete(item_id)
        if not ok:
            return jsonify({"error": "Image not found."}), 404
        return jsonify({"ok": True})

    return app


# WSGI entry point (`gunicorn app.main:app`)
app = create_app()
