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
from rasterio.transform import from_bounds as from_bounds_transform
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds
from fastapi import APIRouter, Response

router = APIRouter()
tms = morecantile.tms.get("WebMercatorQuad")
MERCATOR = "EPSG:3857"

# Dataset cache to avoid opening files repeatedly per request.
# Keyed by layer -> (source, warped view, mtime of the file when it was opened).
_cache_lock = threading.Lock()
_dataset_cache: Dict[str, tuple] = {}
_CACHE_MAX = 16


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


def _close_entry(entry) -> None:
    try:
        entry[0].close()
    except Exception:
        pass


def invalidate_layer_cache(prefix: str = "") -> int:
    """Close and drop cached handles whose layer starts with `prefix` ("" clears all).

    Called before a COG is rebuilt: without it the old dataset stays open and keeps being
    served, so corrected imagery never reaches the map. On Windows the open handle also
    makes the file undeletable.
    """
    with _cache_lock:
        keys = [k for k in _dataset_cache if k.startswith(prefix)] if prefix else list(_dataset_cache)
        for k in keys:
            _close_entry(_dataset_cache.pop(k))
        return len(keys)


def get_cached_dataset(layer: str):
    """Get a cached view of the layer, reprojected to Web Mercator.

    Returns the raw source; reprojection happens per tile in get_tile, because a VRT
    aligned to the tile grid also handles tiles that hang off the edge of the raster.
    """
    path = resolve_layer_path(layer)
    if not path:
        return None
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None

    with _cache_lock:
        entry = _dataset_cache.get(layer)
        # mtime in the key means a rebuilt COG invalidates itself; no manual bookkeeping.
        if entry and entry[1] == mtime and not entry[0].closed:
            return entry[0]
        if entry:
            _close_entry(_dataset_cache.pop(layer))

        try:
            src = rasterio.open(path)
        except Exception:
            return None

        if len(_dataset_cache) >= _CACHE_MAX:
            _close_entry(_dataset_cache.pop(next(iter(_dataset_cache))))
        _dataset_cache[layer] = (src, mtime)
        return src


def get_tile(layer: str, z: int, x: int, y: int) -> bytes:
    """Render a 256x256 PNG tile, reprojecting whatever CRS the raster is in.

    Rasters arrive in whatever CRS the photogrammetry produced — UTM for anything ODM,
    Pix4D or Agisoft emit. Tiles are addressed in Web Mercator. The old code compared tile
    bounds in degrees against the raster's bounds in native units, which was correct only
    by accident on an EPSG:4326 demo raster; every real orthophoto served blank tiles with
    a cheerful HTTP 200.
    """
    src = get_cached_dataset(layer)
    if src is None:
        return EMPTY_TILE_PNG

    tile = morecantile.Tile(x=x, y=y, z=z)
    tile_bounds = tms.xy_bounds(tile)

    try:
        # Intersectia se verifica in Web Mercator, deci limitele sursei se transforma acolo.
        west, south, east, north = transform_bounds(src.crs, MERCATOR, *src.bounds)
        if (
            tile_bounds.left >= east
            or tile_bounds.right <= west
            or tile_bounds.bottom >= north
            or tile_bounds.top <= south
        ):
            return EMPTY_TILE_PNG

        # Un VRT aliniat exact pe tile: reproiecteaza si umple cu transparent in afara
        # rasterului. WarpedVRT nu accepta citiri boundless, iar exceptia aia era inghitita
        # de except-ul de mai jos si iesea tile gol, tacut.
        dst_transform = from_bounds_transform(
            tile_bounds.left, tile_bounds.bottom, tile_bounds.right, tile_bounds.top, 256, 256
        )
        with WarpedVRT(
            src,
            crs=MERCATOR,
            transform=dst_transform,
            width=256,
            height=256,
            resampling=Resampling.bilinear,
        ) as vrt:
            data = vrt.read(out_shape=(src.count, 256, 256))
            alpha = vrt.dataset_mask()

        if data.shape[0] == 3:
            rgba = np.vstack([data, alpha[np.newaxis, ...].astype(np.uint8)])
            return encode_png(rgba)
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
