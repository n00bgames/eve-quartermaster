"""Bounded image validation and lossless storage; no image content in audit logs."""
from io import BytesIO
from uuid import uuid4

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 16_000_000


def normalize_grid_reference(data: bytes) -> tuple[bytes, dict]:
    if not data or len(data) > MAX_BYTES:
        raise HTTPException(413, "Grid image must be between 1 byte and 10 MB.")
    try:
        with Image.open(BytesIO(data)) as source:
            if source.format != "PNG" or source.width * source.height > MAX_PIXELS or getattr(source, "n_frames", 1) != 1:
                raise HTTPException(400, "Upload a single PNG crop of at most 16 megapixels.")
            source.load()
            # Re-encode pixels without metadata or rescaling. Never use lossy compression.
            pixels = source.convert("RGBA" if "A" in source.getbands() or "transparency" in source.info else "RGB")
            pixels.info.clear()
            output = BytesIO()
            pixels.save(output, format="PNG")
            normalized = output.getvalue()
            if len(normalized) > MAX_BYTES:
                raise HTTPException(413, "Selected crop exceeds 10 MB. Select a smaller grid area.")
            return normalized, {"version": uuid4().hex, "width": source.width, "height": source.height, "bytes": len(normalized)}
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise HTTPException(400, "Unable to read the grid screenshot. Try a PNG screenshot.") from exc


def clear_finished_grid_reference(offer) -> None:
    if offer.status == "completed" and (offer.node_map or {}).get("winning_position") is not None:
        offer.grid_reference = None
        offer.grid_reference_data = None
