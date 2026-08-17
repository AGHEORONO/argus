import numpy as np
import pytest
from app.backend.tiles import encode_png, get_tile, EMPTY_TILE_PNG


def test_encode_png():
    # 256x256 RGB
    arr = np.zeros((3, 256, 256), dtype=np.uint8)
    png_bytes = encode_png(arr)
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(png_bytes) > 0


def test_get_tile_empty():
    # Far-away tile coordinates should return valid empty transparent PNG
    png_bytes = get_tile("before", z=10, x=512, y=512)
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(png_bytes) > 0


def test_get_tile_nonexistent_layer():
    png_bytes = get_tile("nonexistent", z=10, x=512, y=512)
    assert png_bytes == EMPTY_TILE_PNG
