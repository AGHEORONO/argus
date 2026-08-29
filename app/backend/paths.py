r"""Unde stau datele — un singur loc care decide, în loc de `os.path.join("data", ...)` presărat.

Până acum fiecare modul construia căi relative la directorul curent. Merge cât timp aplicația
e pornită din rădăcina repo-ului, dar cade în două feluri în afara lui: pornită din alt
director scrie într-un `data/` greșit, iar instalată în `Program Files` nu poate scrie deloc,
fiindcă directorul de instalare e read-only pentru un utilizator obișnuit.

Ordinea de decizie:

1. `ARGUS_DATA_DIR` — explicit, are ultimul cuvânt. Testele și scripturile îl pot fixa.
2. Aplicație împachetată (`sys.frozen`) — `%LOCALAPPDATA%\Argus` pe Windows, `~/.local/share/argus`
   în rest. Scriibil, propriu utilizatorului, supraviețuiește dezinstalării.
3. Altfel `data/` relativ, exact ca înainte — dezvoltarea și testele nu se schimbă.
"""

import os
import sys
from functools import lru_cache


@lru_cache(maxsize=1)
def data_root() -> str:
    explicit = os.environ.get("ARGUS_DATA_DIR")
    if explicit:
        return os.path.abspath(explicit)

    # `sys.frozen` e pus de PyInstaller. `sys._MEIPASS` exista doar in modul one-file, deci
    # nu e un test bun pentru "sunt impachetat".
    if getattr(sys, "frozen", False):
        if sys.platform == "win32":
            baza = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
            return os.path.join(baza, "Argus")
        return os.path.join(os.path.expanduser("~"), ".local", "share", "argus")

    return "data"


def data_path(*parts: str) -> str:
    """O cale în interiorul rădăcinii de date."""
    return os.path.join(data_root(), *parts)


def ensure_data_root() -> str:
    """Creează rădăcina dacă lipsește. De apelat o dată, la pornire."""
    root = data_root()
    os.makedirs(root, exist_ok=True)
    return root


def frontend_dir() -> str | None:
    """Frontendul construit, dacă e livrat împreună cu backendul.

    Există doar în aplicația de desktop: pe web frontendul e servit separat de Vercel.
    Întoarce None când lipsește, iar backendul rămâne API pur.
    """
    candidati = []
    if getattr(sys, "frozen", False):
        # PyInstaller pune datele colectate lângă executabil (one-folder) sau în _MEIPASS
        # (one-file). Amândouă verificate, ca specul să poată alege oricare mod.
        candidati.append(os.path.join(os.path.dirname(sys.executable), "frontend"))
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidati.append(os.path.join(meipass, "frontend"))
    else:
        aici = os.path.dirname(os.path.abspath(__file__))
        radacina = os.path.dirname(os.path.dirname(aici))
        candidati.append(os.path.join(radacina, "app", "frontend", "dist"))

    for c in candidati:
        if os.path.isfile(os.path.join(c, "index.html")):
            return c
    return None
