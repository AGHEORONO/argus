"""The timeline model: a site, several dated captures, comparisons between any two.

The previous model made a "flight" mean a *pair* of rasters, so a comparison could only
ever be the two epochs chosen at upload time. A surveying company flies the same site
repeatedly; the pair is the wrong unit. Here one capture is one flight — one raster, one
date — and any two captures of a site can be compared.
"""

import os
import shutil

import numpy as np
import pytest
import rasterio
from fastapi.testclient import TestClient
from rasterio.transform import from_origin

from app.backend.main import app, get_db

SITE = "pytest_site"
SITE_DIR = os.path.join("data", "sites", SITE)


@pytest.fixture
def client():
    # `with` runs lifespan, which is where the timeline tables are created.
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_site():
    def wipe():
        shutil.rmtree(SITE_DIR, ignore_errors=True)
        with get_db() as conn:
            for table in ("comparisons", "captures", "sites"):
                try:
                    conn.execute(f"DELETE FROM {table} WHERE site_id = ?" if table != "sites"
                                 else "DELETE FROM sites WHERE id = ?", (SITE,))
                except Exception:
                    pass
            conn.commit()

    wipe()
    yield
    wipe()


def raster_bytes(tmp_path, name, bright_square=None):
    """One 300x300 raster near Bucharest, optionally with a bright square painted in."""
    path = str(tmp_path / name)
    transform = from_origin(26.10, 44.42, 0.00002, 0.00002)
    rng = np.random.default_rng(4)
    arr = rng.integers(60, 190, size=(3, 300, 300), dtype=np.uint8)
    if bright_square:
        r0, c0 = bright_square
        arr[:, r0:r0 + 60, c0:c0 + 60] = 250
    with rasterio.open(
        path, "w", driver="GTiff", height=300, width=300, count=3,
        dtype="uint8", crs="EPSG:4326", transform=transform,
    ) as dst:
        dst.write(arr)
    with open(path, "rb") as fh:
        return fh.read()


def add_capture(client, tmp_path, when, name, square=None, label=None):
    data = {"captured_on": when}
    if label:
        data["label"] = label
    res = client.post(
        f"/sites/{SITE}/captures",
        data=data,
        files={"raster": (name, raster_bytes(tmp_path, name, square), "image/tiff")},
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_site_holds_more_than_two_captures(client, tmp_path):
    """The whole point: a timeline longer than a before/after pair."""
    client.post("/sites", data={"site_id": SITE, "name": "Sit de test"})

    add_capture(client, tmp_path, "2026-03-10", "a.tif", label="zbor de referință")
    add_capture(client, tmp_path, "2026-05-18", "b.tif", square=(100, 100))
    add_capture(client, tmp_path, "2026-07-02", "c.tif", square=(180, 60))
    add_capture(client, tmp_path, "2026-09-21", "d.tif", square=(40, 200))

    listed = client.get(f"/sites/{SITE}/captures").json()["captures"]
    assert len(listed) == 4

    dates = [c["captured_on"] for c in listed]
    assert dates == sorted(dates), f"timeline is not chronological: {dates}"
    assert dates[0] == "2026-03-10" and dates[-1] == "2026-09-21"
    assert listed[0]["label"] == "zbor de referință"

    sites = {s["id"]: s for s in client.get("/sites").json()["sites"]}
    assert sites[SITE]["capture_count"] == 4
    assert sites[SITE]["first_capture"] == "2026-03-10"
    assert sites[SITE]["last_capture"] == "2026-09-21"


def test_any_two_captures_can_be_compared(client, tmp_path):
    """Not just consecutive ones: comparing March against September is the question a
    surveyor actually asks."""
    client.post("/sites", data={"site_id": SITE})
    first = add_capture(client, tmp_path, "2026-03-10", "a.tif")
    add_capture(client, tmp_path, "2026-05-18", "b.tif", square=(100, 100))
    last = add_capture(client, tmp_path, "2026-09-21", "d.tif", square=(40, 200))

    res = client.post(
        f"/sites/{SITE}/comparisons",
        data={"base": first["id"], "target": last["id"], "top_n": 5},
    )
    assert res.status_code == 200, res.text
    comparison_id = res.json()["id"]

    detail = client.get(f"/comparisons/{comparison_id}").json()
    assert detail["status"] == "done", detail.get("error_message")
    assert detail["base_capture"] == first["id"]
    assert detail["target_capture"] == last["id"]
    assert detail["result"]["features"], "expected detections between two different rasters"


def test_baseline_is_the_earlier_capture_whatever_the_argument_order(client, tmp_path):
    """Otherwise the same pair could be stored twice with opposite meanings, and 'what
    changed since March' would depend on which box the user filled first."""
    client.post("/sites", data={"site_id": SITE})
    early = add_capture(client, tmp_path, "2026-03-10", "a.tif")
    late = add_capture(client, tmp_path, "2026-09-21", "d.tif", square=(40, 200))

    reversed_order = client.post(
        f"/sites/{SITE}/comparisons",
        data={"base": late["id"], "target": early["id"], "top_n": 3},
    ).json()

    assert reversed_order["base_capture"] == early["id"]
    assert reversed_order["target_capture"] == late["id"]


def test_recomparing_updates_instead_of_duplicating(client, tmp_path):
    """A unique index on the ordered pair; without it, repeated runs pile up rows that
    disagree with each other and the UI has to guess which is current."""
    client.post("/sites", data={"site_id": SITE})
    a = add_capture(client, tmp_path, "2026-03-10", "a.tif")
    b = add_capture(client, tmp_path, "2026-05-18", "b.tif", square=(100, 100))

    first = client.post(f"/sites/{SITE}/comparisons",
                        data={"base": a["id"], "target": b["id"], "top_n": 3}).json()
    second = client.post(f"/sites/{SITE}/comparisons",
                         data={"base": a["id"], "target": b["id"], "top_n": 3}).json()

    assert first["id"] == second["id"]
    listed = client.get(f"/sites/{SITE}/comparisons").json()["comparisons"]
    assert len(listed) == 1


def test_capture_cannot_be_compared_with_itself(client, tmp_path):
    client.post("/sites", data={"site_id": SITE})
    a = add_capture(client, tmp_path, "2026-03-10", "a.tif")
    res = client.post(f"/sites/{SITE}/comparisons",
                      data={"base": a["id"], "target": a["id"]})
    assert res.status_code == 400
    assert "itself" in res.json()["detail"]


def test_unknown_capture_is_named_in_the_error(client, tmp_path):
    client.post("/sites", data={"site_id": SITE})
    a = add_capture(client, tmp_path, "2026-03-10", "a.tif")
    res = client.post(f"/sites/{SITE}/comparisons",
                      data={"base": a["id"], "target": "nu_exista"})
    assert res.status_code == 404
    assert "nu_exista" in res.json()["detail"]


@pytest.mark.parametrize("bad_date", ["ieri", "10-03-2026", "2026-13-45", ""])
def test_non_iso_dates_are_refused(client, tmp_path, bad_date):
    """Dates are stored as text and sorted as text, so a free-form date would silently
    break the chronological ordering the whole timeline depends on."""
    client.post("/sites", data={"site_id": SITE})
    res = client.post(
        f"/sites/{SITE}/captures",
        data={"captured_on": bad_date},
        files={"raster": ("x.tif", raster_bytes(tmp_path, "x.tif"), "image/tiff")},
    )
    assert res.status_code in (400, 422), res.text


def test_capture_on_unknown_site_is_rejected(client, tmp_path):
    res = client.post(
        "/sites/site_inexistent/captures",
        data={"captured_on": "2026-03-10"},
        files={"raster": ("x.tif", raster_bytes(tmp_path, "x.tif"), "image/tiff")},
    )
    assert res.status_code == 404


@pytest.mark.parametrize("hostile", ["..", ".", "a/b", "../../etc"])
def test_site_ids_cannot_escape_their_directory(client, hostile):
    res = client.get(f"/sites/{hostile}/captures")
    assert res.status_code in (400, 404), res.status_code


def test_capture_tiles_serve_that_capture_imagery(client, tmp_path):
    """Without tiles a capture cannot be shown, so the timeline would have nothing to
    cross-fade. Checks pixels, not status codes: an empty tile is also HTTP 200."""
    import io as _io
    import math

    from PIL import Image

    from app.backend.tiles import EMPTY_TILE_PNG, invalidate_layer_cache

    client.post("/sites", data={"site_id": SITE})
    cap = add_capture(client, tmp_path, "2026-03-10", "a.tif", square=(100, 100))

    # The COG is built in a background task; TestClient runs those before returning.
    listed = client.get(f"/sites/{SITE}/captures").json()["captures"][0]
    assert listed["has_tiles"], "COG was not prepared for the capture"
    assert listed["bounds"], "capture has no geographic bounds"

    west, south, east, north = listed["bounds"]
    lon = (west + east) / 2
    lat = (south + north) / 2
    z = 17
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)

    invalidate_layer_cache(SITE)
    res = client.get(f"/tiles/sites/{SITE}/{cap['id']}/{z}/{x}/{y}.png")
    assert res.status_code == 200
    assert res.content != EMPTY_TILE_PNG, "capture served the blank placeholder"

    img = Image.open(_io.BytesIO(res.content)).convert("RGB")
    assert any(hi > lo for lo, hi in img.getextrema()), "tile is a flat colour"


def test_capture_tile_rejects_hostile_ids(client):
    from app.backend.tiles import EMPTY_TILE_PNG

    res = client.get(f"/tiles/sites/../{SITE}/17/1/1.png")
    assert res.status_code in (200, 404)
    if res.status_code == 200:
        assert res.content == EMPTY_TILE_PNG
