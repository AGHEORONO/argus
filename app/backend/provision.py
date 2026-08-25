"""Automated provisioning and seeding of reference rasters and demo flights for ephemeral environments."""

import json
import logging
import os
import urllib.request
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import xy
from rasterio.windows import Window
from rio_cogeo.cogeo import cog_translate
from rio_cogeo.profiles import cog_profiles
from shapely.geometry import Polygon, mapping

from app.backend.detect import detect_changes

# Copiere in benzi de randuri, nu tot rasterul deodata - Render free tier are 512MB RAM,
# iar before.tif intreg (~9000x13000x3) ocupa singur ~335MB per array in memorie.
COPY_CHUNK_ROWS = 512

# Chiar streamed, build_cog (de doua ori) + IsolationForest tot au picat cu OOM pe free
# tier (137, dupa ~2.5 min) - vezi Jurnal 2026-08-21. Reducem rezolutia rasterului demo
# public la download; zonele sintetice de mai jos sunt scalate proportional fata de
# rezolutia originala (T-02: 8959x13066), nu mai sunt constante fixe in pixeli.
MAX_DEMO_DIM = 3000
_ORIG_WIDTH, _ORIG_HEIGHT = 8959, 13066

logger = logging.getLogger("argus.provision")

OAM_DOWNLOAD_URL = (
    "https://oin-hotosm-temp.s3.amazonaws.com/58d86fafca8ed70011209f81/0/"
    "113fb2f2-d8dc-425a-97c2-20050a580192.tif"
)

REF_DIR = "data/reference"
BEFORE_PATH = os.path.join(REF_DIR, "before.tif")
AFTER_PATH = os.path.join(REF_DIR, "after.tif")
BEFORE_COG_PATH = os.path.join(REF_DIR, "before.cog.tif")
AFTER_COG_PATH = os.path.join(REF_DIR, "after.cog.tif")
TRUTH_PATH = os.path.join(REF_DIR, "truth.geojson")


def ensure_reference_data():
    """Ensure baseline orthophoto, synthetic comparison raster, and COGs exist on disk."""
    os.makedirs(REF_DIR, exist_ok=True)

    # 1. Download before.tif if missing
    if not os.path.exists(BEFORE_PATH):
        logger.info(f"Downloading reference orthophoto from {OAM_DOWNLOAD_URL}...")
        urllib.request.urlretrieve(OAM_DOWNLOAD_URL, BEFORE_PATH)
        logger.info(f"Downloaded {BEFORE_PATH} ({os.path.getsize(BEFORE_PATH)} bytes)")

    downsample_if_needed(BEFORE_PATH, MAX_DEMO_DIM)

    # 2. Generate after.tif and truth.geojson if missing
    if not os.path.exists(AFTER_PATH) or not os.path.exists(TRUTH_PATH):
        logger.info("Generating synthetic after.tif and truth.geojson...")
        generate_synthetic_pair()

    # 3. Build COGs if missing
    if not os.path.exists(BEFORE_COG_PATH):
        logger.info("Building before.cog.tif...")
        build_cog(BEFORE_PATH, BEFORE_COG_PATH)

    if not os.path.exists(AFTER_COG_PATH):
        logger.info("Building after.cog.tif...")
        build_cog(AFTER_PATH, AFTER_COG_PATH)


def downsample_if_needed(path: str, max_dim: int):
    """Shrink a raster in place so its longest side is at most max_dim, using GDAL's
    decimated read (resamples while streaming source blocks - never materializes the
    full-resolution array). No-op if already small enough. Idempotent."""
    with rasterio.open(path) as src:
        width, height = src.width, src.height
        scale = max_dim / max(width, height)
        if scale >= 1.0:
            return

        new_width = max(1, round(width * scale))
        new_height = max(1, round(height * scale))
        profile = src.profile.copy()
        transform = src.transform * src.transform.scale(width / new_width, height / new_height)
        profile.update(width=new_width, height=new_height, transform=transform)
        data = src.read(out_shape=(src.count, new_height, new_width), resampling=Resampling.average)

    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data)

    logger.info(f"Downsampled {path} to {new_width}x{new_height} (was {width}x{height})")


def build_cog(src_path: str, dst_path: str):
    """Convert standard GeoTIFF to Cloud Optimized GeoTIFF with Deflate compression and overviews."""
    profile = cog_profiles.get("deflate")
    profile.update({"BIGTIFF": "IF_NEEDED", "BLOCKXSIZE": 256, "BLOCKYSIZE": 256})
    cog_translate(
        src_path,
        dst_path,
        profile,
        in_memory=False,
        quiet=True,
    )


def generate_synthetic_pair():
    """Generate synthetic modifications on before.tif to create after.tif and truth.geojson.

    Streamed in row-chunks + small per-zone windows (never the full raster in memory) -
    Render free tier has 512MB RAM, and the full array would alone take ~335MB.
    """
    with rasterio.open(BEFORE_PATH) as src:
        profile = src.profile.copy()
        transform = src.transform
        crs = src.crs
        width, height = src.width, src.height

        # Zonele de mai jos au fost desenate la rezolutia originala (T-02: 8959x13066).
        # Daca before.tif a fost redus (vezi downsample_if_needed), scalam proportional -
        # altfel coordonatele ar cadea in afara imaginii sau ar deforma zonele.
        sw = width / _ORIG_WIDTH
        sh = height / _ORIG_HEIGHT

        def scaled(r0, r1, c0, c1):
            return (round(r0 * sh), round(r1 * sh), round(c0 * sw), round(c1 * sw))

        with rasterio.open(AFTER_PATH, "w", **profile) as dst:
            for row0 in range(0, height, COPY_CHUNK_ROWS):
                rows = min(COPY_CHUNK_ROWS, height - row0)
                window = Window(0, row0, width, rows)
                dst.write(src.read(window=window), window=window)

    # Seed fixat: setul sintetic e gandit ca test de regresie stabil intre masini
    # (vezi Plan de implementare.md), deci zgomotul injectat trebuie sa fie reproductibil.
    rng = np.random.default_rng(42)

    with rasterio.open(AFTER_PATH, "r+") as dst:
        # Zone 1: Structure removal (uniform pavement patch). Media se calculeaza din
        # banda de deasupra zonei, inca neatinsa - citita direct din after.tif proaspat copiat.
        r1, r2, c1, c2 = scaled(1200, 1500, 2000, 2350)
        surround_rows = max(1, round(50 * sh))
        surround = dst.read(window=Window(c1, max(0, r1 - surround_rows), c2 - c1, surround_rows))
        mean_surrounding = np.mean(surround, axis=(1, 2), keepdims=True)
        zone1_window = Window(c1, r1, c2 - c1, r2 - r1)
        zone1_shape = (dst.count, r2 - r1, c2 - c1)
        zone1 = np.clip(mean_surrounding + rng.normal(0, 3, zone1_shape), 0, 255).astype(np.uint8)
        dst.write(zone1, window=zone1_window)

        # Zone 2: Blue storage container / new structure - fill uniform, nu are nevoie sa citeasca
        r3, r4, c3, c4 = scaled(3000, 3250, 4500, 4800)
        zone2_window = Window(c3, r3, c4 - c3, r4 - r3)
        zone2_hw = (r4 - r3, c4 - c3)
        dst.write(np.full(zone2_hw, 30, dtype=np.uint8), 1, window=zone2_window)
        dst.write(np.full(zone2_hw, 90, dtype=np.uint8), 2, window=zone2_window)
        dst.write(np.full(zone2_hw, 210, dtype=np.uint8), 3, window=zone2_window)

        # Zone 3: Vegetation clearing (dry bare ground)
        r5, r6, c5, c6 = scaled(5000, 5400, 1500, 1900)
        zone3_window = Window(c5, r5, c6 - c5, r6 - r5)
        zone3 = dst.read(window=zone3_window).astype(np.float64)
        zone3[0] = np.clip(zone3[0] * 1.4 + 20, 0, 255)
        zone3[1] = np.clip(zone3[1] * 0.7 - 10, 0, 255)
        zone3[2] = np.clip(zone3[2] * 0.6 - 15, 0, 255)
        dst.write(zone3.astype(np.uint8), window=zone3_window)

        # Zone 4: Excavation trench (dark shadow interior, bright excavated edge)
        r7, r8, c7, c8 = scaled(2200, 2800, 6000, 6150)
        zone4a_window = Window(c7, r7, c8 - c7, r8 - r7)
        zone4a = np.clip(dst.read(window=zone4a_window).astype(np.float64) * 0.25, 0, 255)
        dst.write(zone4a.astype(np.uint8), window=zone4a_window)

        edge_width = max(1, round(40 * sw))
        zone4b_window = Window(c8, r7, edge_width, r8 - r7)
        zone4b = np.clip(dst.read(window=zone4b_window).astype(np.float64) * 1.5 + 40, 0, 255)
        dst.write(zone4b.astype(np.uint8), window=zone4b_window)

    # Build truth.geojson
    def make_poly(rmin, rmax, cmin, cmax):
        x0, y0 = xy(transform, rmin, cmin, offset="ul")
        x1, y1 = xy(transform, rmax, cmax, offset="ul")
        return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])

    zones = [
        {"id": "zone_1", "desc": "Structure removal", "bounds": (r1, r2, c1, c2)},
        {"id": "zone_2", "desc": "New blue structure/container", "bounds": (r3, r4, c3, c4)},
        {"id": "zone_3", "desc": "Vegetation clearing", "bounds": (r5, r6, c5, c6)},
        {"id": "zone_4", "desc": "Excavation trench and mound", "bounds": (r7, r8, c7, c8 + edge_width)},
    ]

    features = []
    for z in zones:
        poly = make_poly(*z["bounds"])
        features.append({
            "type": "Feature",
            "id": z["id"],
            "properties": {"description": z["desc"], "pixel_bounds": list(z["bounds"])},
            "geometry": mapping(poly),
        })

    truth_doc = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": crs.to_string() if crs else "EPSG:4326"}},
        "features": features,
    }

    with open(TRUTH_PATH, "w", encoding="utf-8") as f:
        json.dump(truth_doc, f, indent=2)


def _result_matches_raster(result_json: str) -> bool:
    """True when a stored detection could have come from the raster currently on disk.

    downsample_if_needed rewrites before.tif in place, but the seed returns early whenever
    the flight is already 'done' — so after a resolution change the demo kept serving
    detections computed on a raster that no longer existed. Locally that silently halved
    recall, from 4 of 4 known changes to 2 of 4, with nothing to indicate anything was wrong.
    A patch index beyond what the current raster can hold is proof of the mismatch.
    """
    try:
        doc = json.loads(result_json)
        features = doc.get("features") or []
        if not features:
            return False
        highest = max(f.get("properties", {}).get("patch_index", 0) for f in features)
        with rasterio.open(BEFORE_PATH) as src:
            available = (src.width // 32) * (src.height // 32)
        if highest >= available:
            logger.info(
                "Stored demo result references patch %d but the raster holds %d; recomputing.",
                highest, available,
            )
            return False
        return True
    except Exception as exc:
        logger.warning("Could not validate stored demo result (%s); recomputing.", exc)
        return False


def seed_demo_flight(get_db_func):
    """Ensure flight 'test' is present in database and pre-processed for instant demo viewing."""
    ensure_reference_data()

    with get_db_func() as conn:
        cursor = conn.execute("SELECT id, status, result FROM flights WHERE id = 'test'")
        row = cursor.fetchone()

        if row and row["status"] == "done" and row["result"] and _result_matches_raster(row["result"]):
            logger.info("Demo flight 'test' already seeded and done.")
            return

        logger.info("Computing change detection for demo flight 'test'...")
        result = detect_changes(BEFORE_PATH, AFTER_PATH, top_n=50)
        result_json = json.dumps(result)

        conn.execute(
            """
            INSERT INTO flights (id, status, before_path, after_path, result)
            VALUES ('test', 'done', ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = 'done',
                before_path = excluded.before_path,
                after_path = excluded.after_path,
                result = excluded.result,
                error_message = NULL,
                updated_at = CURRENT_TIMESTAMP
            """,
            (BEFORE_PATH, AFTER_PATH, result_json),
        )
        conn.commit()
        logger.info("Demo flight 'test' seeded successfully.")
