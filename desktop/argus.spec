# -*- mode: python ; coding: utf-8 -*-
"""Impachetare PyInstaller, mod one-folder.

Partea supăratoare a stivei ăsteia e geospatialul: `rasterio` isi aduce propriile DLL-uri de
GDAL intr-un director `rasterio.libs`, iar `pyproj` are nevoie de `proj.db`, fara de care
orice reproiectare cade la rulare cu o eroare care nu spune ce lipseste. Amandoua se
colecteaza explicit mai jos; niciunul nu e gasit de analiza automata.

One-folder, nu one-file: `--onefile` dezarhiveaza ~300MB in temp la FIECARE pornire (10-20s
de asteptare de fiecare data) si e forma care declanseaza cel mai des euristica antivirusului.
"""

import os

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

RADACINA = os.path.abspath(os.path.join(SPECPATH, ".."))
FRONTEND = os.path.join(RADACINA, "app", "frontend", "dist")

if not os.path.isfile(os.path.join(FRONTEND, "index.html")):
    raise SystemExit(
        "Frontendul nu e construit. Ruleaza intai:\n"
        "  cd app/frontend && npx vite build --mode desktop\n"
        "Fara el, aplicatia porneste si arata o pagina alba."
    )

datas = [(FRONTEND, "frontend")]
for pachet in ("rasterio", "pyproj", "rio_cogeo", "morecantile", "sklearn", "scipy"):
    datas += collect_data_files(pachet)

binaries = []
for pachet in ("rasterio", "pyproj"):
    binaries += collect_dynamic_libs(pachet)

hiddenimports = []
for pachet in ("rasterio", "pyproj", "uvicorn", "sklearn.ensemble", "sklearn.utils"):
    hiddenimports += collect_submodules(pachet)
hiddenimports += [
    # pywebview alege backendul GUI dinamic, deci analiza statica nu-l vede.
    "webview.platforms.edgechromium",
    "clr_loader",
]

a = Analysis(
    [os.path.join(SPECPATH, "argus_desktop.py")],
    pathex=[RADACINA],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    excludes=[
        # Nu intra in program: unelte de dezvoltare care ar adauga zeci de MB degeaba.
        "pytest", "playwright", "PyInstaller", "tkinter", "matplotlib", "IPython",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Argus Custode",
    debug=False,
    strip=False,
    upx=False,          # UPX pe DLL-urile de GDAL le strica, si creste alarmele antivirus
    console=False,      # fara fereastra neagra de consola; erorile merg in jurnal
    # .ico multi-rezolutie, cu desene separate per dimensiune: sub 24 px conturul de 1,5 al
    # marcii ajunge sub un pixel si se spala, deci acolo se foloseste varianta plina.
    icon=os.path.join(RADACINA, "app", "frontend", "public", "icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Argus Custode",
)
