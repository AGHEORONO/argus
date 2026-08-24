"""Dynamic tile serving for Cloud Optimized GeoTIFFs (COG) with dataset caching and Pillow."""

import io
import os
import threading
from typing import Dict, Optional
import morecantile
import numpy as np
from PIL import Image
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import from_bounds
from fastapi import APIRouter, Response

router = APIRouter()
tms = morecantile.tms.get("WebMercatorQuad")

# Dataset cache to avoid opening files repeatedly per request
_cache_lock = threading.Lock()
_dataset_cache: Dict[str, rasterio.DatasetReader] = {}


def encode_png(data: np.ndarray) -> bytes:
    """Encode an RGB (3, H, W), RGBA (4, H, W), or 2D numpy array to PNG bytes using Pillow."""
    if data.ndim == 3:
        if data.shape[0] == 4:
            img = Image.fromarray(np.transpose(data, (1, 2, 0)), mode="RGBA")
        elif data.shape[0] == 3:
            img = Image.fromarray(np.transpose(data, (1, 2, 0)), mode="RGB")
        else:
            img = Image.fromarray(data[0], mode="L")
    else:
        img = Image.fromarray(data, mode="L")

    buf = io.BytesIO()
    img.save(buf, format="PNG", compress_level=1)
    return buf.getvalue()


# Pre-cached empty 256x256 transparent PNG
EMPTY_TILE_PNG = encode_png(np.zeros((4, 256, 256), dtype=np.uint8))


def resolve_layer_path(layer: str) -> Optional[str]:
    """Find the COG or GeoTIFF path for a given layer name."""
    candidates = [
        f"data/reference/{layer}.cog.tif",
        f"data/reference/{layer}.tif",
        # Forma "<flight_id>/<before|after>", folosita de ruta pe zbor. Varianta veche
        # "<flight_id>/<flight_id>.cog.tif" nu era produsa de nimic — uploadul scrie
        # before.tif/after.tif — deci tile-urile pentru zboruri urcate nu functionau.
        os.path.join("data", "flights", f"{layer}.cog.tif"),
        os.path.join("data", "flights", f"{layer}.tif"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def get_cached_dataset(layer: str) -> Optional[rasterio.DatasetReader]:
    """Get or open a cached rasterio dataset handle."""
    with _cache_lock:
        if layer in _dataset_cache:
            ds = _dataset_cache[layer]
            if not ds.closed:
                return ds

        path = resolve_layer_path(layer)
        if not path:
            return None

        ds = rasterio.open(path)
        _dataset_cache[layer] = ds
        return ds


def get_tile(layer: str, z: int, x: int, y: int) -> bytes:
    """Retrieve and render a 256x256 PNG tile from a cached raster dataset."""
    ds = get_cached_dataset(layer)
    if ds is None:
        return EMPTY_TILE_PNG

    tile = morecantile.Tile(x=x, y=y, z=z)
    tile_bounds = tms.bounds(tile)

    try:
        # Check bounding box intersection in WGS84
        rb = ds.bounds
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
            transform=ds.transform,
        )

        data = ds.read(
            window=window,
            out_shape=(ds.count, 256, 256),
            resampling=Resampling.bilinear,
            boundless=True,
            fill_value=0,
        )

        if data.shape[0] == 3:
            mask = (data > 0).any(axis=0).astype(np.uint8) * 255
            rgba = np.vstack([data, mask[np.newaxis, ...]])
            return encode_png(rgba)
        elif data.shape[0] == 4:
            return encode_png(data)
        else:
            return encode_png(data)

    except Exception:
        return EMPTY_TILE_PNG


def _tile_response(png_bytes: bytes) -> Response:
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


# Ruta pe zbor sta INAINTEA celei generice: literalul "flights" nu se poate confunda cu un
# nume de layer, deci nu exista ambiguitate de rutare intre cele doua.
@router.get("/tiles/flights/{flight_id}/{layer}/{z}/{x}/{y}.png")
def render_flight_tile(flight_id: str, layer: str, z: int, x: int, y: int):
    """Serve raster tiles for one uploaded flight's own before/after imagery."""
    if layer not in ("before", "after"):
        return _tile_response(EMPTY_TILE_PNG)
    # Numele de fisier se construieste din flight_id, deci se aplica aceleasi restrictii
    # ca la restul cailor: fara separatori, fara '.' sau '..'.
    if (
        not flight_id
        or flight_id in (".", "..")
        or os.path.basename(flight_id.replace("\\", "/")) != flight_id
    ):
        return _tile_response(EMPTY_TILE_PNG)
    return _tile_response(get_tile(os.path.join(flight_id, layer), z, x, y))


@router.get("/tiles/{layer}/{z}/{x}/{y}.png")
def render_tile(layer: str, z: int, x: int, y: int):
    """Serve raster tiles for map clients with low latency."""
    return _tile_response(get_tile(layer, z, x, y))
