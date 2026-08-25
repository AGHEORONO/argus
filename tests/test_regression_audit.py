"""Tests for the failure modes a fresh-eyes audit found, each of which passed the old suite.

Every test here asserts an ANSWER, not a shape. The suite this joins had 27 green tests
coexisting with a tile server that served blank tiles for every real-world CRS, a detector
that reported five anomalies for zero change, and COGs that were never rebuilt. Those
survived because the tests checked that a FeatureCollection was a FeatureCollection and
that a PNG started with a PNG magic number.
"""

import json
import os
import shutil

import numpy as np
import pytest
import rasterio
from PIL import Image
from rasterio.transform import from_origin

from app.backend.detect import detect_changes
from app.backend.tiles import EMPTY_TILE_PNG, get_tile, invalidate_layer_cache

REF_DIR = "data/reference"
BEFORE = os.path.join(REF_DIR, "before.tif")
AFTER = os.path.join(REF_DIR, "after.tif")
TRUTH = os.path.join(REF_DIR, "truth.geojson")

needs_reference = pytest.mark.skipif(
    not (os.path.exists(BEFORE) and os.path.exists(AFTER)),
    reason="reference rasters not provisioned",
)


def write_raster(path, crs, transform, arr):
    with rasterio.open(
        path, "w", driver="GTiff", height=arr.shape[1], width=arr.shape[2],
        count=arr.shape[0], dtype=arr.dtype, crs=crs, transform=transform,
    ) as dst:
        dst.write(arr)


def synthetic_pair(tmp_path, crs, transform, size=256):
    """A raster and a copy with one bright square painted into it."""
    rng = np.random.default_rng(7)
    base = rng.integers(60, 190, size=(3, size, size), dtype=np.uint8)
    changed = base.copy()
    changed[:, 150:190, 150:190] = 250

    a = str(tmp_path / "before.tif")
    b = str(tmp_path / "after.tif")
    write_raster(a, crs, transform, base)
    write_raster(b, crs, transform, changed)
    return a, b


# ── Detection returns coordinates the rest of the system can actually use ──────────

def test_detection_output_is_wgs84_even_for_utm_input(tmp_path):
    """A UTM orthophoto — what ODM, Pix4D and Agisoft all produce — used to emit
    coordinates in metres that the frontend rendered as degrees: "4919103 grade nord"."""
    transform = from_origin(428500.0, 4919500.0, 3.2, 3.2)
    a, b = synthetic_pair(tmp_path, "EPSG:32635", transform)

    result = detect_changes(a, b, patch=32, top_n=5)
    assert result["features"], "expected detections on an injected change"

    for feature in result["features"]:
        for lon, lat in feature["geometry"]["coordinates"][0]:
            assert -180 <= lon <= 180, f"longitude out of range: {lon}"
            assert -90 <= lat <= 90, f"latitude out of range: {lat}"

    # The site is near Bucharest; assert we land there rather than merely in-range.
    lon, lat = result["features"][0]["geometry"]["coordinates"][0][0]
    assert 25.9 < lon < 26.3, lon
    assert 44.3 < lat < 44.6, lat


def test_rfc7946_has_no_crs_member(tmp_path):
    """RFC 7946 removed the `crs` member; carrying one made the un-reprojected
    coordinates look intentional rather than broken."""
    transform = from_origin(428500.0, 4919500.0, 3.2, 3.2)
    a, b = synthetic_pair(tmp_path, "EPSG:32635", transform)
    result = detect_changes(a, b, patch=32, top_n=3)
    assert "crs" not in result
    assert result.get("source_crs") == "EPSG:32635"


# ── Detection is allowed to find nothing ──────────────────────────────────────────

def test_identical_rasters_yield_no_anomalies(tmp_path):
    """Isolation Forest scores every patch exactly 0.5 when nothing stands out. The old
    code returned top_n candidates anyway, so an unchanged flight produced confident
    false positives. Note the score is 0.5000000000000002, so the threshold needs a
    tolerance — a strict `> 0.5` lets it through."""
    transform = from_origin(26.10, 44.42, 0.00003, 0.00003)
    rng = np.random.default_rng(3)
    arr = rng.integers(60, 190, size=(3, 256, 256), dtype=np.uint8)
    a = str(tmp_path / "same_a.tif")
    b = str(tmp_path / "same_b.tif")
    write_raster(a, "EPSG:4326", transform, arr)
    write_raster(b, "EPSG:4326", transform, arr)

    result = detect_changes(a, b, patch=32, top_n=10)
    assert result["features"] == []


def test_real_change_is_still_found(tmp_path):
    """Guard against the previous test being satisfied by a detector that finds nothing."""
    transform = from_origin(26.10, 44.42, 0.00003, 0.00003)
    a, b = synthetic_pair(tmp_path, "EPSG:4326", transform)
    result = detect_changes(a, b, patch=32, top_n=10)
    assert len(result["features"]) > 0
    assert all(f["properties"]["anomaly_score"] > 0.5 for f in result["features"])


def test_detection_lands_on_the_patch_that_changed(tmp_path):
    """The old test of the core algorithm asserted only that a FeatureCollection came
    back with `top_n` features — it passed with after == before."""
    transform = from_origin(26.10, 44.42, 0.00003, 0.00003)
    a, b = synthetic_pair(tmp_path, "EPSG:4326", transform)
    result = detect_changes(a, b, patch=32, top_n=5)

    # The square was painted at rows/cols 150-190, i.e. patch rows/cols 4 and 5.
    hit = False
    for feature in result["features"]:
        r0, r1, c0, c1 = feature["properties"]["pixel_bounds"]
        if r0 < 190 and r1 > 150 and c0 < 190 and c1 > 150:
            hit = True
            break
    assert hit, "top detections did not overlap the region that actually changed"


@needs_reference
def test_recall_against_truth_geojson():
    """truth.geojson has existed since T-03 and was never used by a test; recall was
    measured by hand. The local demo silently regressed from 4/4 to 2/4 without any
    test noticing."""
    if not os.path.exists(TRUTH):
        pytest.skip("truth.geojson not provisioned")

    with open(TRUTH, encoding="utf-8") as fh:
        truth = json.load(fh)

    result = detect_changes(BEFORE, AFTER, top_n=50)
    boxes = []
    for feature in result["features"]:
        ring = feature["geometry"]["coordinates"][0]
        lons = [p[0] for p in ring]
        lats = [p[1] for p in ring]
        boxes.append((min(lons), min(lats), max(lons), max(lats)))

    found = 0
    for zone in truth["features"]:
        ring = zone["geometry"]["coordinates"][0]
        zlon0, zlon1 = min(p[0] for p in ring), max(p[0] for p in ring)
        zlat0, zlat1 = min(p[1] for p in ring), max(p[1] for p in ring)
        if any(
            b[0] < zlon1 and b[2] > zlon0 and b[1] < zlat1 and b[3] > zlat0
            for b in boxes
        ):
            found += 1

    total = len(truth["features"])
    assert found >= 3, f"recall dropped to {found}/{total} of the known changes"


# ── Tiles carry pixels, and carry them for real-world projections ─────────────────

@needs_reference
def test_tile_has_actual_pixel_content():
    """No test asserted a tile had pixels. `get_tile` returns EMPTY_TILE_PNG on every
    failure path, so a test that only checks the PNG magic number cannot fail — which is
    how a completely blank tile server stayed green."""
    import math

    lon, lat, z = -78.4309, 0.0140, 16
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)

    png = get_tile("before", z, x, y)
    assert png != EMPTY_TILE_PNG, "tile server returned the blank placeholder"

    import io as _io

    img = Image.open(_io.BytesIO(png)).convert("RGB")
    extrema = img.getextrema()
    assert any(hi > lo for lo, hi in extrema), f"tile is a flat colour: {extrema}"


def test_tiles_work_for_a_non_wgs84_raster(tmp_path, monkeypatch):
    """Tile bounds are Web Mercator; the raster is in whatever CRS photogrammetry emitted.
    The old code compared degrees against native units and served blank tiles with HTTP
    200 for every UTM orthophoto — i.e. every real one."""
    import math

    flight = "pytest_utm_flight"
    flight_dir = os.path.join("data", "flights", flight)
    os.makedirs(flight_dir, exist_ok=True)
    try:
        transform = from_origin(428500.0, 4919500.0, 1.0, 1.0)
        rng = np.random.default_rng(11)
        arr = rng.integers(40, 220, size=(3, 800, 800), dtype=np.uint8)
        write_raster(os.path.join(flight_dir, "before.cog.tif"), "EPSG:32635", transform, arr)

        # Centre of that UTM block is about 26.106 E, 44.421 N.
        lon, lat, z = 26.1065, 44.4215, 16
        n = 2 ** z
        x = int((lon + 180.0) / 360.0 * n)
        y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)

        invalidate_layer_cache(flight)
        png = get_tile(f"{flight}/before", z, x, y)
        assert png != EMPTY_TILE_PNG, "UTM raster served a blank tile"

        import io as _io

        img = Image.open(_io.BytesIO(png)).convert("RGB")
        assert any(hi > lo for lo, hi in img.getextrema())
    finally:
        invalidate_layer_cache(flight)
        shutil.rmtree(flight_dir, ignore_errors=True)


def test_cache_serves_rebuilt_imagery(tmp_path):
    """The cache held an open handle forever and `build_flight_cogs` skipped any COG that
    already existed. After correcting a flight's imagery the operator saw the OLD raster
    with the NEW anomaly boxes drawn on it, reported as done."""
    import math

    flight = "pytest_rebuild_flight"
    flight_dir = os.path.join("data", "flights", flight)
    os.makedirs(flight_dir, exist_ok=True)
    cog = os.path.join(flight_dir, "before.cog.tif")
    try:
        transform = from_origin(26.10, 44.42, 0.00002, 0.00002)
        lon, lat, z = 26.1050, 44.4190, 17
        n = 2 ** z
        x = int((lon + 180.0) / 360.0 * n)
        y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)

        magenta = np.zeros((3, 800, 800), dtype=np.uint8)
        magenta[0], magenta[2] = 220, 220
        write_raster(cog, "EPSG:4326", transform, magenta)
        invalidate_layer_cache(flight)
        first = get_tile(f"{flight}/before", z, x, y)
        assert first != EMPTY_TILE_PNG

        cyan = np.zeros((3, 800, 800), dtype=np.uint8)
        cyan[1], cyan[2] = 220, 220
        invalidate_layer_cache(f"{flight}/before")
        write_raster(cog, "EPSG:4326", transform, cyan)
        # Force a distinct mtime even on coarse-resolution filesystems.
        os.utime(cog, (os.path.getmtime(cog) + 5, os.path.getmtime(cog) + 5))

        second = get_tile(f"{flight}/before", z, x, y)
        assert second != first, "tile server kept serving the superseded imagery"
    finally:
        invalidate_layer_cache(flight)
        shutil.rmtree(flight_dir, ignore_errors=True)


def test_concurrent_tile_requests_are_consistent():
    """GDAL datasets are not thread-safe, and uvicorn runs sync endpoints in a threadpool,
    so several tile requests hit the same cached handle at once. That segfaulted the whole
    process — and, more insidiously, produced reads that failed silently and came out as
    blank tiles, because the handler swallows every exception into EMPTY_TILE_PNG.
    """
    import math
    import threading

    if not os.path.exists(BEFORE):
        pytest.skip("reference rasters not provisioned")

    lon, lat, z = -78.4309, 0.0140, 16
    n = 2 ** z
    bx = int((lon + 180.0) / 360.0 * n)
    by = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)
    coords = [(bx + i, by + j) for i in range(3) for j in range(3)]

    invalidate_layer_cache()
    sequential = sum(
        1 for tx, ty in coords if get_tile("before", z, tx, ty) != EMPTY_TILE_PNG
    )
    assert sequential > 0, "no real tiles even sequentially; fixture problem"

    invalidate_layer_cache()
    hits = []
    errors = []
    guard = threading.Lock()

    def worker():
        try:
            for _ in range(5):
                for tx, ty in coords:
                    if get_tile("before", z, tx, ty) != EMPTY_TILE_PNG:
                        with guard:
                            hits.append(1)
        except Exception as exc:  # pragma: no cover - only on regression
            errors.append(repr(exc))

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, errors
    assert len(hits) == sequential * 5 * 6, (
        f"concurrent access lost tiles: got {len(hits)}, expected {sequential * 5 * 6}"
    )
