"""Argus Custode ca aplicatie Windows de sine statatoare.

Aceeasi aplicatie, doar impachetata altfel: backendul FastAPI porneste pe un port local ales
la rulare, serveste si frontendul construit din aceeasi origine, iar interfata se deschide
intr-o fereastra proprie peste WebView2 (Edge), nu intr-un tab de browser.

WebView2 e Chromium, deci NVDA, navigarea de la tastatura si contrastul se comporta identic
cu ce e verificat de suita din `app/frontend/tests-e2e/`. Asta a fost si motivul alegerii:
o interfata nativa rescrisa ar fi aruncat toata munca aia.

Portul se alege liber, nu fix: doua instante pornite din greseala, sau orice alt program pe
8000, ar face pornirea sa esueze cu un mesaj pe care nimeni nu-l vede intr-o aplicatie fara
consola.
"""

import logging
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request

from app.backend.paths import data_root, ensure_data_root

TITLU = "Argus Custode"
GAZDA = "127.0.0.1"


def _porneste_jurnalul() -> str:
    """Jurnal pe disc, langa date.

    Intr-o aplicatie fara consola, o exceptie la pornire dispare fara urma. Fisierul asta e
    singurul lucru care poate fi cerut utilizatorului cand raporteaza ca 'nu porneste'.
    """
    ensure_data_root()
    cale = os.path.join(data_root(), "argus-desktop.log")
    logging.basicConfig(
        filename=cale,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        force=True,
    )
    return cale


def port_liber() -> int:
    """Un port pe care sistemul confirma ca e liber chiar acum."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((GAZDA, 0))
        return s.getsockname()[1]


def porneste_serverul(port: int):
    """Uvicorn intr-un fir separat, ca firul principal sa ramana al ferestrei.

    Intors ca obiect, nu doar pornit: inchiderea ferestrei trebuie sa poata cere oprirea,
    altfel procesul ramane in Task Manager dupa ce utilizatorul crede ca a inchis programul.
    """
    import uvicorn

    from app.backend.main import app

    # log_config=None e OBLIGATORIU aici, nu o preferinta. Configuratia implicita a lui
    # uvicorn instaleaza un formatter colorat care intreaba `sys.stdout.isatty()`, iar
    # intr-o aplicatie construita cu console=False `sys.stdout` este None:
    #   AttributeError: 'NoneType' object has no attribute 'isatty'
    # Aplicatia murea la pornire exact aici, si fara jurnal nu se vedea de ce. Oricum avem
    # jurnal propriu pe fisier, deci nu pierdem nimic.
    config = uvicorn.Config(
        app, host=GAZDA, port=port, log_level="warning", access_log=False, log_config=None,
    )
    server = uvicorn.Server(config)

    def ruleaza():
        # O exceptie intr-un fir nu se propaga nicaieri: fara `except` aici, serverul moare
        # in tacere, iar aplicatia asteapta 90 de secunde un raspuns care nu vine niciodata
        # si raporteaza "nu a raspuns la timp" — un simptom, nu cauza. S-a intamplat exact
        # asa la prima rulare a pachetului construit.
        try:
            server.run()
        except BaseException:
            logging.exception("serverul s-a oprit cu eroare")
            server.should_exit = True

    fir = threading.Thread(target=ruleaza, name="argus-uvicorn", daemon=True)
    fir.start()
    return server, fir


def asteapta_serverul(port: int, secunde: float = 90.0) -> bool:
    """Asteapta un raspuns real, nu doar un port deschis.

    Prima pornire poate dura: daca lipsesc datele demo, backendul le pregateste inainte sa
    raspunda. Se interogheaza /api, care nu depinde de existenta frontendului.
    """
    limita = time.monotonic() + secunde
    while time.monotonic() < limita:
        try:
            with urllib.request.urlopen(f"http://{GAZDA}:{port}/api", timeout=3) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.4)
    return False


def _deschide_in_browser(url: str) -> None:
    """Varianta de rezerva cand WebView2 lipseste.

    Mai bine o fereastra de browser decat un program care nu porneste. Firul principal ramane
    blocat aici, altfel procesul s-ar incheia si ar opri serverul chiar sub pagina deschisa.
    """
    import webbrowser

    logging.warning("WebView2 indisponibil, se deschide browserul implicit")
    webbrowser.open(url)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


def main() -> int:
    jurnal = _porneste_jurnalul()
    logging.info("pornire; date in %s", data_root())
    try:
        return _main(jurnal)
    except BaseException:
        # Intr-o aplicatie construita cu console=False, `sys.stderr` e None: un traceback
        # nescris in jurnal nu ajunge nicaieri, iar simptomul vizibil e un program care pur
        # si simplu nu porneste. S-a intamplat de doua ori la primele rulari ale pachetului.
        logging.exception("pornire esuata")
        _arata_eroare(_mesaj_esec(jurnal))
        return 1


def _main(jurnal: str) -> int:

    port = port_liber()
    url = f"http://{GAZDA}:{port}/"
    server, _ = porneste_serverul(port)

    if not asteapta_serverul(port):
        logging.error("backendul nu a raspuns la timp")
        _arata_eroare(
            "Argus nu a putut porni.\n\n"
            f"Detaliile sunt in:\n{jurnal}"
        )
        return 1

    logging.info("backend gata pe %s", url)

    # Fara fereastra: verificarea pachetului construit. PyInstaller construieste usor, dar
    # GDAL cade la RULARE — de exemplu cand lipseste proj.db. Singurul mod de a sti ca
    # executabilul chiar merge e sa-i ceri un tile, ceea ce trece prin rasterio, GDAL si
    # proiectie. Vezi `tests/test_desktop_bundle.py`.
    if os.environ.get("ARGUS_NO_WINDOW"):
        logging.info("mod fara fereastra; se serveste pana la oprire")
        try:
            while not server.should_exit:
                time.sleep(0.5)
        except KeyboardInterrupt:
            server.should_exit = True
        return 0

    try:
        import webview
    except ImportError:
        _deschide_in_browser(url)
        return 0

    fereastra = webview.create_window(
        TITLU,
        url,
        width=1440,
        height=900,
        min_size=(360, 600),  # sub 320px reflow-ul nu mai e testat, deci nici permis
        text_select=True,     # un raport care nu se poate copia nu e un raport
    )

    def la_inchidere():
        logging.info("fereastra inchisa, se opreste serverul")
        server.should_exit = True

    fereastra.events.closed += la_inchidere

    try:
        # gui='edgechromium' explicit: pe o masina cu MSHTML disponibil, pywebview ar putea
        # cadea pe Internet Explorer, unde aplicatia nici nu se randeaza.
        webview.start(gui="edgechromium")
    except Exception:
        logging.exception("WebView2 a esuat")
        _deschide_in_browser(url)

    server.should_exit = True
    return 0


def _mesaj_esec(jurnal: str) -> str:
    """Textul aratat cand pornirea esueaza. Construit din bucati, fara secvente de evadare."""
    return os.linesep.join([
        "Argus nu a putut porni.",
        "",
        "Detaliile sunt in:",
        jurnal,
    ])


def _arata_eroare(mesaj: str) -> None:
    """Un mesaj vizibil, nu doar o linie in jurnal.

    MessageBoxW e MODAL: fara nimeni care sa apese OK, blocheaza procesul la nesfarsit. In
    modul fara fereastra (teste, rulare automata) mesajul merge doar pe stderr si in jurnal.
    """
    logging.error(" ".join(mesaj.split()))
    if os.environ.get("ARGUS_NO_WINDOW"):
        print(mesaj, file=sys.stderr)
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, mesaj, TITLU, 0x10)
    except Exception:
        print(mesaj, file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
