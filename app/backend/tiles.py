"""Dynamic tile serving for Cloud Optimized GeoTIFFs (COG)."""

import os
import struct
import zlib
from typing import Optional
import morecantile
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import from_bounds
from fastapi import APIRouter, HTTPException, Response

router = APIRouter()
tms = morecantile.tms.get("WebMercatorQuad")


def encode_png(data: np.ndarray) -> bytes:
    """Encode an RGB (3, H, W) or RGBA (4, H, W) numpy array to PNG bytes quickly."""
    if data.ndim == 3 and data.shape[0] in (1, 3, 4):
        data = np.transpose(data, (1, 2, 0))
    H, W, C = data.shape
    color_type = 6 if C == 4 else (2 if C == 3 else 0)

    lines = bytearray()
    for row in data:
        lines.append(0)  # Filter type None
        lines.extend(row.tobytes())

    compressed = zlib.compress(bytes(lines), level=1)

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    png = bytearray(b"\x89PNG\r\n\x1a\n")
    ihdr = struct.pack(">IIBBBBB", W, H, 8, color_type, 0, 0, 0)
    png.extend(chunk(b"IHDR", ihdr))
    png.extend(chunk(b"IDAT", compressed))
    png.extend(chunk(b"IEND", b""))
    return bytes(png)


# Cached 256x256 transparent PNG for empty / non-overlapping tiles
EMPTY_TILE_PNG = encode_png(np.zeros((256, 256, 4), dtype=np.uint8))


def resolve_layer_path(layer: str) -> Optional[str]:
    """Find the COG or GeoTIFF path for a given layer name."""
    candidates = [
        f"data/reference/{layer}.cog.tif",
        f"data/reference/{layer}.tif",
        f"data/flights/{layer}/{layer}.cog.tif",
        f"data/flights/{layer}/{layer}.tif",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def get_tile(layer: str, z: int, x: int, y: int) -> bytes:
    """Retrieve and render a 256x256 PNG tile from a raster."""
    path = resolve_layer_path(layer)
    if not path:
        return EMPTY_TILE_PNG

    tile = morecantile.Tile(x=x, y=y, z=z)
    tile_bounds = tms.bounds(tile)

    try:
        with rasterio.open(path) as src:
            # Check bounding box intersection in WGS84
            rb = src.bounds
            if (
                tile_bounds.left > rb.right
                or tile_bounds.right < rb.left
                or tile_bounds.bottom > rb.top
                or tile_bounds.top < rb.bottom
            ):
                return EMPTY_TILE_PNG

            window = from_bounds(
                tile_bounds.left,
                tile_bounds.bottom,
                tile_bounds.right,
                tile_bounds.top,
                transform=src.transform,
            )

            data = src.read(
                window=window,
                out_shape=(src.count, 256, 256),
                resampling=Resampling.bilinear,
                boundless=True,
                fill_value=0,
            )

            # If 3 channels, add alpha channel based on non-zero pixels
            if data.shape[0] == 3:
                mask = (data > 0).any(axis=0).astype(np.uint8) * 255
                rgba = np.vstack([data, mask[np.newaxis, ...]])
                return encode_png(rgba)
            elif data.shape[0] == 4:
                return encode_png(data)
            else:
                return encode_png(data[:3])

    except Exception:
        return EMPTY_TILE_PNG


@router.get("/tiles/{layer}/{z}/{x}/{y}.png")
def render_tile(layer: str, z: int, x: int, y: int):
    """Serve raster tiles for map clients."""
    png_bytes = get_tile(layer, z, x, y)
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )
