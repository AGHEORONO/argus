"""Pornirea aplicației de desktop, verificată fără să deschidă o fereastră.

Fereastra e ultimul pas și cel mai puțin interesant. Ce se poate strica tăcut e tot ce se
întâmplă înainte: alegerea portului, pornirea serverului într-un fir, așteptarea lui, și
faptul că aceeași origine servește și pagina și API-ul.

Fără testul ăsta, singurul mod de a afla că launcher-ul e rupt e să construiești executabilul
și să dai dublu-clic.
"""

import os
import urllib.request

import pytest

from app.backend.paths import frontend_dir
from desktop import argus_desktop as app_desktop


def cere(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.headers.get("content-type", ""), r.read()


@pytest.fixture(scope="module")
def server_pornit():
    port = app_desktop.port_liber()
    server, fir = app_desktop.porneste_serverul(port)
    gata = app_desktop.asteapta_serverul(port, secunde=90)
    yield port, gata
    server.should_exit = True
    fir.join(timeout=15)


def test_portul_ales_e_chiar_liber():
    """Două instanțe pornite din greșeală nu au voie să se blocheze una pe alta."""
    a, b = app_desktop.port_liber(), app_desktop.port_liber()
    assert a > 1024 and b > 1024
    # Nu se cere să fie diferite — sistemul poate reoferi același port după ce l-a eliberat —
    # ci doar ca fiecare să fie chiar legabil în momentul întoarcerii.
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((app_desktop.GAZDA, a))


def test_serverul_raspunde_dupa_pornire(server_pornit):
    port, gata = server_pornit
    assert gata, "backendul nu a răspuns în 90s"
    stare, _, _ = cere(f"http://{app_desktop.GAZDA}:{port}/api")
    assert stare == 200


def test_aceeasi_origine_serveste_si_pagina_si_api(server_pornit):
    """Motivul pentru care aplicația de desktop nu are nevoie de CORS."""
    port, gata = server_pornit
    assert gata
    baza = f"http://{app_desktop.GAZDA}:{port}"

    if not frontend_dir():
        pytest.skip("frontendul nu e construit (app/frontend/dist lipsește)")

    stare, tip, corp = cere(f"{baza}/")
    assert stare == 200
    assert "text/html" in tip
    assert b"<div id=\"root\"" in corp or b"<div id='root'" in corp

    stare_api, _, _ = cere(f"{baza}/flights")
    assert stare_api == 200


def test_jurnalul_se_scrie_langa_date(tmp_path, monkeypatch):
    """Într-o aplicație fără consolă, jurnalul e singura urmă a unei porniri eșuate."""
    from app.backend import paths

    paths.data_root.cache_clear()
    monkeypatch.setenv("ARGUS_DATA_DIR", str(tmp_path / "date"))
    try:
        cale = app_desktop._porneste_jurnalul()
        assert os.path.dirname(cale) == os.path.abspath(str(tmp_path / "date"))
        assert os.path.isdir(os.path.dirname(cale))
    finally:
        paths.data_root.cache_clear()
        import logging

        logging.basicConfig(force=True)
