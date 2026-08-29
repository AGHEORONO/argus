"""Ține backendul simulat din testele de interfață lipit de backendul adevărat.

Testele Playwright din `app/frontend/tests-e2e/` nu pornesc backendul: îi simulează
răspunsurile din `tests-e2e/fixtures.json`. Câștigul e că testele de interfață rulează în
secunde și pot forța stări greu de atins (zero rezultate, lipsa adevărului de referință).
Costul e că simularea se poate depărta de API fără ca nimeni să observe — interfața ar
rămâne verde în timp ce producția servește altceva.

Testul ăsta e puntea. Ia cheile din fișierul de fixtures și cere backendului adevărat să le
producă. Dacă cineva redenumește `captured_on` sau scoate `anomaly_score`, aici pică, nu în
producție.

Nu verifică valorile, doar formele: valorile din fixtures sunt inventate intenționat.
"""

import json
import os
import shutil
import sqlite3

import numpy as np
import pytest
import rasterio
from fastapi.testclient import TestClient
from rasterio.transform import from_origin

from app.backend.main import app, get_db

SITE = "pytest_contract"
SITE_DIR = os.path.join("data", "sites", SITE)
FLIGHT = "pytest_contract_flight"
FIXTURES = os.path.join("app", "frontend", "tests-e2e", "fixtures.json")


@pytest.fixture(scope="module")
def fixtures():
    assert os.path.exists(FIXTURES), (
        f"{FIXTURES} lipsește. Testele de interfață îl citesc, deci dacă a fost mutat, "
        "puntea asta nu mai verifică nimic."
    )
    with open(FIXTURES, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clean():
    def wipe():
        shutil.rmtree(SITE_DIR, ignore_errors=True)
        shutil.rmtree(os.path.join("data", "flights", FLIGHT), ignore_errors=True)
        # Tolerant la tabele lipsă: fixture-ul autouse rulează înaintea `client`, deci la
        # primul test tabelele de timeline încă nu există — ele se creează în lifespan.
        with get_db() as conn:
            for sql, arg in (
                ("DELETE FROM comparisons WHERE site_id = ?", SITE),
                ("DELETE FROM captures WHERE site_id = ?", SITE),
                ("DELETE FROM sites WHERE id = ?", SITE),
                ("DELETE FROM flights WHERE id = ?", FLIGHT),
            ):
                try:
                    conn.execute(sql, (arg,))
                except sqlite3.OperationalError:
                    pass
            conn.commit()

    wipe()
    yield
    wipe()


def raster_bytes(tmp_path, name, square=None):
    path = str(tmp_path / name)
    rng = np.random.default_rng(7)
    arr = rng.integers(60, 190, size=(3, 200, 200), dtype=np.uint8)
    if square:
        r0, c0 = square
        arr[:, r0:r0 + 50, c0:c0 + 50] = 250
    with rasterio.open(
        path, "w", driver="GTiff", height=200, width=200, count=3,
        dtype="uint8", crs="EPSG:4326", transform=from_origin(26.10, 44.42, 0.00002, 0.00002),
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


def lipsesc(asteptate, primite):
    """Cheile pe care le folosește frontendul și API-ul nu le mai dă."""
    return sorted(set(asteptate) - set(primite))


def test_lista_de_capturi_are_formele_din_fixtures(client, tmp_path, fixtures):
    client.post("/sites", data={"site_id": SITE})
    add_capture(client, tmp_path, "2026-03-10", "a.tif", label="zbor de referință")
    add_capture(client, tmp_path, "2026-05-18", "b.tif", square=(80, 80))

    real = client.get(f"/sites/{SITE}/captures").json()

    assert not lipsesc(["site_id", "captures"], real), \
        f"plicul răspunsului a pierdut chei: {lipsesc(['site_id', 'captures'], real)}"

    asteptate = fixtures["captures"][0].keys()
    absente = lipsesc(asteptate, real["captures"][0])
    assert not absente, (
        f"o captură reală nu mai are {absente}. `fixtures.json` le folosește, deci "
        "testele de interfață verifică o formă care nu mai există."
    )


def test_lista_de_comparatii_are_formele_din_fixtures(client, tmp_path, fixtures):
    client.post("/sites", data={"site_id": SITE})
    a = add_capture(client, tmp_path, "2026-03-10", "a.tif")
    b = add_capture(client, tmp_path, "2026-05-18", "b.tif", square=(80, 80))
    client.post(f"/sites/{SITE}/comparisons", data={"base": a["id"], "target": b["id"], "top_n": 3})

    real = client.get(f"/sites/{SITE}/comparisons").json()
    assert "comparisons" in real
    assert real["comparisons"], "comparația tocmai creată nu apare în listă"

    asteptate = fixtures["comparisons"][0].keys()
    absente = lipsesc(asteptate, real["comparisons"][0])
    assert not absente, f"o comparație reală nu mai are {absente}"


def test_anomaliile_reale_au_proprietatile_pe_care_le_deseneaza_frontendul(client, tmp_path, fixtures):
    """`rank` și `anomaly_score` ajung direct în textul citit cu voce tare."""
    client.post("/sites", data={"site_id": SITE})
    a = add_capture(client, tmp_path, "2026-03-10", "a.tif")
    b = add_capture(client, tmp_path, "2026-05-18", "b.tif", square=(80, 80))
    cid = client.post(
        f"/sites/{SITE}/comparisons", data={"base": a["id"], "target": b["id"], "top_n": 3}
    ).json()["id"]

    detaliu = client.get(f"/comparisons/{cid}").json()
    assert detaliu["status"] == "done", detaliu.get("error_message")
    features = detaliu["result"]["features"]
    assert features, "detecția n-a produs nicio anomalie între două rastere diferite"

    asteptate = fixtures["anomaly_properties"].keys()
    absente = lipsesc(asteptate, features[0]["properties"])
    assert not absente, (
        f"o anomalie reală nu mai are {absente}. Frontendul le citește în panoul accesibil."
    )
    assert features[0]["geometry"]["type"] == "Polygon"


def test_lista_de_zboruri_are_formele_din_fixtures(client, tmp_path, fixtures):
    res = client.post(
        "/flights",
        data={"flight_id": FLIGHT},
        files={
            "before": ("before.tif", raster_bytes(tmp_path, "before.tif"), "image/tiff"),
            "after": ("after.tif", raster_bytes(tmp_path, "after.tif", square=(80, 80)), "image/tiff"),
        },
    )
    assert res.status_code == 200, res.text

    zboruri = client.get("/flights").json()
    assert "flights" in zboruri
    real = next((f for f in zboruri["flights"] if f["id"] == FLIGHT), None)
    assert real is not None, "zborul tocmai încărcat nu apare în listă"

    asteptate = fixtures["flights"][0].keys()
    absente = lipsesc(asteptate, real)
    assert not absente, f"un zbor real nu mai are {absente}"


def test_fixtures_nu_pretinde_chei_pe_care_nu_le_foloseste_nimeni(fixtures):
    """Invers față de restul: fixtures să nu crească necontrolat.

    O cheie inventată în fixtures, pe care backendul n-o dă niciodată, e o minciună pe care
    testele de interfață o cred. Lista de mai jos e verificată de celelalte teste; asta doar
    se asigură că fișierul n-a căpătat între timp secțiuni pe care nimeni nu le compară.
    """
    verificate = {"captures", "comparisons", "flights", "anomaly_properties"}
    netestate = set(fixtures) - verificate - {"_comentariu", "site", "truth_properties"}
    assert not netestate, (
        f"secțiuni noi în fixtures.json fără punte spre backend: {sorted(netestate)}. "
        "Adaugă un test aici sau scoate-le."
    )
