"""Automated provisioning and seeding of reference rasters and demo flights for ephemeral environments."""

import json
import logging
import os
import urllib.request
import numpy as np
import rasterio
from rasterio.transform import xy
from rio_cogeo.cogeo import cog_translate
from rio_cogeo.profiles import cog_profiles
from shapely.geometry import Polygon, mapping

from app.backend.detect import detect_changes

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
    """Generate synthetic modifications on before.tif to create after.tif and truth.geojson."""
    with rasterio.open(BEFORE_PATH) as src:
        profile = src.profile.copy()
        data = src.read()
        transform = src.transform
        crs = src.crs

    after_data = data.copy()
    c, h, w = after_data.shape

    # Seed fixat: setul sintetic e gandit ca test de regresie stabil intre masini
    # (vezi Plan de implementare.md), deci zgomotul injectat trebuie sa fie reproductibil.
    rng = np.random.default_rng(42)

    # Zone 1: Structure removal (uniform pavement patch)
    r1, r2, c1, c2 = 1200, 1500, 2000, 2350
    mean_surrounding = np.mean(after_data[:, r1 - 50 : r1, c1:c2], axis=(1, 2), keepdims=True)
    after_data[:, r1:r2, c1:c2] = np.clip(
        mean_surrounding + rng.normal(0, 3, (c, r2 - r1, c2 - c1)), 0, 255
    ).astype(np.uint8)

    # Zone 2: Blue storage container / new structure
    r3, r4, c3, c4 = 3000, 3250, 4500, 4800
    after_data[0, r3:r4, c3:c4] = 30
    after_data[1, r3:r4, c3:c4] = 90
    after_data[2, r3:r4, c3:c4] = 210

    # Zone 3: Vegetation clearing (dry bare ground)
    r5, r6, c5, c6 = 5000, 5400, 1500, 1900
    after_data[0, r5:r6, c5:c6] = np.clip(after_data[0, r5:r6, c5:c6] * 1.4 + 20, 0, 255)
    after_data[1, r5:r6, c5:c6] = np.clip(after_data[1, r5:r6, c5:c6] * 0.7 - 10, 0, 255)
    after_data[2, r5:r6, c5:c6] = np.clip(after_data[2, r5:r6, c5:c6] * 0.6 - 15, 0, 255)

    # Zone 4: Excavation trench (dark shadow interior, bright excavated edge)
    r7, r8, c7, c8 = 2200, 2800, 6000, 6150
    after_data[:, r7:r8, c7:c8] = np.clip(after_data[:, r7:r8, c7:c8] * 0.25, 0, 255)
    after_data[:, r7:r8, c8 : c8 + 40] = np.clip(after_data[:, r7:r8, c8 : c8 + 40] * 1.5 + 40, 0, 255)

    with rasterio.open(AFTER_PATH, "w", **profile) as dst:
        dst.write(after_data)

    # Build truth.geojson
    def make_poly(rmin, rmax, cmin, cmax):
        x0, y0 = xy(transform, rmin, cmin, offset="ul")
        x1, y1 = xy(transform, rmax, cmax, offset="ul")
        return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])

    zones = [
        {"id": "zone_1", "desc": "Structure removal", "bounds": (r1, r2, c1, c2)},
        {"id": "zone_2", "desc": "New blue structure/container", "bounds": (r3, r4, c3, c4)},
        {"id": "zone_3", "desc": "Vegetation clearing", "bounds": (r5, r6, c5, c6)},
        {"id": "zone_4", "desc": "Excavation trench and mound", "bounds": (r7, r8, c7, c8 + 40)},
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


def seed_demo_flight(get_db_func):
    """Ensure flight 'test' is present in database and pre-processed for instant demo viewing."""
    ensure_reference_data()

    with get_db_func() as conn:
        cursor = conn.execute("SELECT id, status, result FROM flights WHERE id = 'test'")
        row = cursor.fetchone()

        if row and row["status"] == "done" and row["result"]:
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
