"""Executabilul construit chiar funcționează?

PyInstaller construiește ușor. Ce cade e rularea: `rasterio` își aduce propriile DLL-uri de
GDAL, `pyproj` are nevoie de `proj.db`, și niciunul nu e găsit de analiza automată. Lipsa lor
nu se vede la build — se vede când prima reproiecție eșuează, adică exact la primul tile.

De aceea testul cere un TILE, nu pagina de start. O pagină servită dovedește doar că uvicorn
pornește. Un tile dovedește că lanțul geospatial e întreg în pachet.

Se sare când pachetul nu e construit: nu se construiește în CI, unde ar dura minute și ar
produce 300 MB pentru fiecare push.
"""

import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request

import pytest

RADACINA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(RADACINA, "dist-desktop", "Argus Custode", "Argus Custode.exe")
REFERINTA = os.path.join(RADACINA, "data", "reference")

pytestmark = pytest.mark.skipif(
    not os.path.isfile(EXE),
    reason="pachetul nu e construit — rulează .\build-desktop.ps1",
)


def _citeste_url(jurnal, limita=180, proc=None):
    """Portul e ales la rulare, deci singura sursă e jurnalul aplicației.

    Se renunță imediat ce procesul a murit: altfel o pornire eșuată costă trei minute de
    așteptare per rulare, iar mesajul de la final spune doar că n-a venit nimic.
    """
    sfarsit = time.monotonic() + limita
    while time.monotonic() < sfarsit:
        if proc is not None and proc.poll() is not None:
            return None
        if os.path.isfile(jurnal):
            with open(jurnal, encoding="utf-8", errors="replace") as fh:
                m = re.search(r"backend gata pe (http://\S+)", fh.read())
            if m:
                return m.group(1).rstrip("/")
        time.sleep(1)
    return None


@pytest.fixture(scope="module")
def aplicatie_pornita(tmp_path_factory):
    date = tmp_path_factory.mktemp("date-desktop")
    if not os.path.isdir(REFERINTA):
        pytest.skip("lipsesc rasterele demo din data/reference")
    shutil.copytree(REFERINTA, os.path.join(str(date), "reference"))

    mediu = dict(os.environ)
    # `conftest.py` fixeaza ARGUS_DB_PATH ca sa tina pytest departe de baza de productie, iar
    # mediul se mosteneste in copil: fara stergerea asta, aplicatia impachetata ar scrie in
    # baza de date a testelor si ar ignora radacina de date pe care tocmai i-am dat-o.
    mediu.pop("ARGUS_DB_PATH", None)
    mediu["ARGUS_DATA_DIR"] = str(date)
    mediu["ARGUS_NO_WINDOW"] = "1"
    mediu["ARGUS_SKIP_SEED"] = "1"

    proc = subprocess.Popen([EXE], env=mediu, cwd=str(date))
    url = _citeste_url(os.path.join(str(date), "argus-desktop.log"), proc=proc)
    yield url, proc, str(date)

    proc.terminate()
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()


def cere(url, timeout=60):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.headers.get("content-type", ""), r.read()


def test_executabilul_porneste_si_raspunde(aplicatie_pornita):
    url, proc, _ = aplicatie_pornita
    assert url, "aplicația nu a scris niciodată adresa în jurnal — vezi argus-desktop.log"
    assert proc.poll() is None, "procesul a murit după pornire"
    stare, _, _ = cere(f"{url}/api")
    assert stare == 200


def test_pagina_si_apiul_vin_din_aceeasi_origine(aplicatie_pornita):
    url, _, _ = aplicatie_pornita
    assert url
    stare, tip, corp = cere(f"{url}/")
    assert stare == 200 and "text/html" in tip
    # Bundle-ul de desktop nu are voie să conțină adresa absolută de dezvoltare: ar cere de la
    # alt port decât cel pe care rulează, iar aplicația ar arăta o hartă goală.
    activ = re.search(rb'src="(/assets/[^"]+\.js)"', corp)
    assert activ, "index.html nu referă niciun bundle"
    _, _, js = cere(f"{url}{activ.group(1).decode()}")
    assert b"127.0.0.1:8000" not in js, "bundle-ul a fost construit fără --mode desktop"


def test_un_tile_chiar_se_randeaza_din_pachet(aplicatie_pornita):
    """Proba de foc: trece prin rasterio, DLL-urile de GDAL și proj.db.

    Zborul demo `test` citește `reference/before.cog.tif`, copiat în directorul de date al
    testului. Un PNG întors înseamnă că lanțul geospatial e complet în pachet.
    """
    url, _, _ = aplicatie_pornita
    assert url
    zboruri = cere(f"{url}/flights")[2]
    assert b"flights" in zboruri

    stare, tip, corp = cere(f"{url}/tiles/before/16/18869/32762.png")
    assert stare == 200, f"tile-ul a eșuat: {stare}"
    assert "image/png" in tip
    assert corp[:8] == b"\x89PNG\r\n\x1a\n", "răspunsul nu e un PNG valid"
    assert len(corp) > 200, "PNG suspect de mic — probabil tile complet gol"


def test_datele_se_scriu_unde_i_s_a_spus(aplicatie_pornita):
    """Într-o instalare reală directorul programului e read-only."""
    _, _, date = aplicatie_pornita
    assert os.path.isfile(os.path.join(date, "argus-desktop.log"))
    assert os.path.isfile(os.path.join(date, "argus.db")), \
        "baza de date nu a fost creată în rădăcina de date indicată"
