---
tags: [argus, taskuri, executie]
created: 2026-08-17
type: taskuri
---

# Task-uri de start

Proiect: [[Argus Custode]]. Sprintul 1 = faza 4 + faza 6 din [[Plan de implementare]].

Scrise ca să poată fi executate de un model ieftin și rapid (Sonnet, Gemini Flash) fără decizii de arhitectură. Citește întâi [[Reguli pentru agent executant]]. Regula unică: **un task nu e terminat până output-ul checkului nu e lipit în [[Jurnal]]**.

Ordine strict secvențială. Fiecare task e un commit.

---

## T-01 — Schelet și mediu

**Obiectiv**: `app/` există, mediul Python e reproductibil pe altă mașină.

**Fă**:
```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install numpy rasterio scikit-learn shapely fastapi uvicorn rio-cogeo pytest
pip freeze > app/requirements.txt
```
Structura: `app/backend/`, `app/frontend/`, `app/backend/__init__.py`.

**Check**:
```
python -c "import numpy, rasterio, sklearn, shapely; print('imports OK')"
python check.py
```

**Terminat când**: ambele comenzi ies cu cod 0 și `app/requirements.txt` are versiuni fixate (`==`, nu `>=`).

**Rollback**: `rm -rf app .venv`

---

## T-02 — Ortofotoplan public de test

**Obiectiv**: un GeoTIFF real, georeferențiat, în `data/reference/`.

**Fă**: descarcă un ortofotoplan de dronă de pe OpenAerialMap, filtrat pe licență permisivă. Salvează ca `data/reference/before.tif`. `data/` e în `.gitignore` — fișierul **nu** intră în git.

**Check** — scrie `app/backend/inspect_raster.py`, care printează și validează cu `assert`:
```
python app/backend/inspect_raster.py data/reference/before.tif
```
Trebuie să treacă: CRS diferit de `None`, lățime și înălțime > 2000 px, minim 3 benzi, rezoluție per pixel < 0.5 m.

**Terminat când**: scriptul printează metadatele fără să pice pe assert, iar `python check.py` confirmă că niciun `.tif` nu e urmărit de git.

**Rollback**: șterge fișierul, nu e în istoric.

---

## T-03 — Perechea sintetică cu adevăr cunoscut

**Obiectiv**: din `before.tif` generezi `after.tif` cu N schimbări injectate, plus `truth.geojson` care spune exact unde sunt. Fără asta nu poți măsura nimic în T-05.

**Fă**: `app/backend/make_synthetic.py`, cu semnătura `make_synthetic(src, dst, truth_out, n=10, seed=42)`.
Fiecare schimbare: un dreptunghi la poziție aleatoare (seed fix, deci reproductibil) în care aplici una din trei operații — umpli cu o culoare plată (obiect nou), copiezi o zonă din altă parte a imaginii (obiect mutat), sau schimbi hue-ul (vegetație modificată). Georeferențierea din `before.tif` se păstrează identică.

**Check** — self-check cu `assert` în `if __name__ == "__main__"`:
- `truth.geojson` are exact N poligoane, toate valide
- pixelii din **interiorul** poligoanelor diferă între before și after
- pixelii din **exteriorul** poligoanelor sunt identici bit-cu-bit (`np.array_equal`)
- transform și CRS identice între before și after

```
python app/backend/make_synthetic.py
```

**Terminat când**: toate assert-urile trec. Ultimul e cel care contează — dacă pică, algoritmul din T-05 va fi măsurat pe zgomot.

**Rollback**: `git revert` pe commit, șterge `after.tif` și `truth.geojson`.

---

## T-04 — Features per patch, vectorizat

**Obiectiv**: dintr-un raster, o matrice de features, un rând per patch. **Zero bucle Python peste patch-uri** — vezi [[Performanta]].

**Fă**: `app/backend/features.py`, funcția `patch_features(path, patch=32) -> (array, transform)`.
Features per patch: media pe fiecare bandă, deviația standard pe fiecare bandă, magnitudinea medie a gradientului. Reshape în blocuri (`arr.reshape(h//p, p, w//p, p)`) și reduce pe axe — nu iterezi.

**Check** — `app/backend/test_features.py`:
- pe o imagine sintetică uniformă, deviația standard e ~0 pe toate patch-urile
- pe o imagine cu jumătate neagră și jumătate albă, mediile separă patch-urile în exact două grupuri
- numărul de rânduri = `(h//p) * (w//p)`
- timp pe raster de test sub 10 secunde (`assert` pe durată)

```
python -m pytest app/backend/test_features.py -q
```

**Terminat când**: pytest verde. Timpul măsurat se scrie în [[Jurnal]] — e prima cifră reală de performanță.

**Rollback**: `git revert`.

---

## T-05 — Detecția și măsurarea ei

**Obiectiv**: Isolation Forest antrenat pe before, aplicat pe after, output GeoJSON cu scoruri. Și, mai important, **cifra de recall**.

**Fă**: `app/backend/detect.py` cu `detect(before, after, patch=32, contamination=0.02) -> GeoJSON`.
Antrenezi pe features din before, scorezi patch-urile din after, convertești patch-urile anormale în poligoane georeferențiate cu scor.

**Check** — `app/backend/test_detect.py`, evaluat pe perechea din T-03:
- din cele 10 zone injectate, cel puțin 8 sunt atinse de un patch din top-20 scoruri (recall ≥ 0.8)
- rulează în sub 30 de secunde
- GeoJSON valid, cu CRS și cu `score` pe fiecare feature

```
python -m pytest app/backend/test_detect.py -q
```

**Terminat când**: recall-ul măsurat e scris în [[Jurnal]] ca cifră, nu ca „funcționează". Dacă e sub 0.8, ajustezi `patch` și `contamination` — sunt parametri, nu constante. Dacă după 3 încercări e tot sub, oprește-te și scrie în jurnal ce ai încercat.

**Rollback**: `git revert`.

---

## T-06 — COG și servire tile-uri

**Obiectiv**: raster mare afișabil fluid, fără pre-tiling.

**Fă**: convertește la Cloud Optimized GeoTIFF cu `rio cogeo create`. Servirea se face din COG cu titiler, nu din tile-uri pre-generate. Motivul e în [[Performanta]].

**Check**:
```
rio cogeo validate data/reference/before_cog.tif
```
Plus măsoară latența unui request de tile și scrie cifra în jurnal.

**Terminat când**: validate trece, latența e sub 150 ms local.

**Rollback**: șterge COG-ul, sursa e neatinsă.

---

## T-07 — API minim

**Obiectiv**: patru endpoint-uri, nimic în plus.

**Fă**: `app/backend/main.py` — `GET /health`, `POST /detect` (pornește job), `GET /jobs/{id}` (status), `GET /results/{id}` (GeoJSON). Job asincron cu `BackgroundTasks`, stare în SQLite cu WAL activat.

**Check** — `app/backend/test_api.py` cu `TestClient`:
- `/health` întoarce 200
- un job trece prin stările `pending` → `running` → `done`
- `/results` întoarce GeoJSON valid
- un id inexistent întoarce 404, nu 500

```
python -m pytest app/backend/test_api.py -q
```

**Terminat când**: pytest verde, inclusiv cazul de 404.

**Rollback**: `git revert`.

---

## T-08 — Hartă și slider

**Obiectiv**: partea care se vede la prezentare.

**Fă**: React/Vite + MapLibre GL. Layer raster din COG, overlay GeoJSON colorat după scor, slider before/after peste aceeași zonă. Sliderul modifică `raster-opacity`, **nu** reîncarcă sursa.

**Check**: manual, plus captură de ecran salvată în `CodeVault/raw/` și pusă în [[Jurnal]]. Verifică explicit: harta rămâne fluidă la zoom, poligoanele stau fix peste raster când muți harta.

**Terminat când**: captura există în jurnal și `python check.py` trece.

**Rollback**: `git revert`.

---

## După T-08

MVP-ul e complet și demonstrabil, fără să fi atins vreodată o dronă. De aici: fazele 1, 2, 7 din [[Plan de implementare]], în funcție de răspunsurile din [[Intrebari deschise]].
