"""Convert a PNG image into a print-ready PDF centered on the selected paper."""

from __future__ import annotations

import io
from typing import Literal

from PIL import Image

PaperSize = Literal["A4", "Letter"]

# Pixel dimensions at 300 DPI
_PAPER_PX = {
    "A4": (2480, 3508),        # 210 x 297 mm
    "Letter": (2550, 3300),    # 8.5 x 11 in
}

_MARGIN_RATIO = 0.05  # 5% margin on each side


def png_to_pdf(png_bytes: bytes, paper: PaperSize = "A4") -> bytes:
    """Fit a PNG onto a single-page PDF of the requested paper size.

    The source image is scaled to fit within the page while preserving aspect
    ratio, then pasted centered on a white page. Output is a single-page PDF.
    """
    paper_w, paper_h = _PAPER_PX.get(paper, _PAPER_PX["A4"])
    margin = int(min(paper_w, paper_h) * _MARGIN_RATIO)
    printable_w = paper_w - 2 * margin
    printable_h = paper_h - 2 * margin

    src = Image.open(io.BytesIO(png_bytes))
    # Flatten to white background if the PNG has alpha
    if src.mode in ("RGBA", "LA") or (src.mode == "P" and "transparency" in src.info):
        rgba = src.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[-1])
        src = bg
    else:
        src = src.convert("RGB")

    # Scale preserving aspect ratio
    src_ratio = src.width / src.height
    page_ratio = printable_w / printable_h
    if src_ratio > page_ratio:
        new_w = printable_w
        new_h = int(printable_w / src_ratio)
    else:
        new_h = printable_h
        new_w = int(printable_h * src_ratio)
    scaled = src.resize((new_w, new_h), Image.LANCZOS)

    page = Image.new("RGB", (paper_w, paper_h), (255, 255, 255))
    offset_x = (paper_w - new_w) // 2
    offset_y = (paper_h - new_h) // 2
    page.paste(scaled, (offset_x, offset_y))

    buf = io.BytesIO()
    page.save(buf, format="PDF", resolution=300.0)
    return buf.getvalue()
