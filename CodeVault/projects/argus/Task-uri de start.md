---
tags: [argus, taskuri, executie]
created: 2026-08-17
type: taskuri
---

# Task-uri de start

Proiect: [[Argus Custode]]. Sprintul 1 = faza 4 + faza 6 din [[Plan de implementare]] (detecție de schimbări + hartă), pe ordinea de atac **4 → 6 → 5 → 3**.

Scrise ca să poată fi executate de un model rapid și ieftin (Sonnet, Gemini Flash prin `agy`) fără decizii de arhitectură — deciziile sunt deja luate în [[Decizii]], aici nu se redeschid. Un task nu e terminat până output-ul checkului nu e lipit în [[Jurnal]]. Ordine strict secvențială, un commit per task, mesaj `T-0X: ce s-a făcut` — commit-ul îl face Claude, după revizuire, nu agentul de execuție.

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
```

**Terminat când**: comanda de mai sus iese cu cod 0 și `app/requirements.txt` are versiuni fixate (`==`, nu `>=`).

**Rollback**: `rm -rf app .venv`

---

## T-02 — Ortofotoplan public de test

**Obiectiv**: un GeoTIFF real, georeferențiat, în `data/reference/`.

**Fă**: descarcă un ortofotoplan de dronă de pe OpenAerialMap, filtrat pe licență permisivă. Salvează ca `data/reference/before.tif`. `data/` e în `.gitignore` — fișierul **nu** intră în git.

**Check**:
```
python -c "import rasterio; d = rasterio.open('data/reference/before.tif'); print(d.crs, d.width, d.height)"
```

**Terminat când**: CRS-ul e valid (nu `None`) și dimensiunile sunt de ordinul miilor de pixeli pe latură.

**Rollback**: `rm -rf data/reference`

---

## T-03 — Perechea sintetică before/after

**Obiectiv**: `data/reference/after.tif`, o copie a lui `before.tif` cu schimbări injectate manual, plus `data/reference/truth.geojson` cu poligoanele exacte unde s-a modificat.

**Fă**: duplică `before.tif`. Editează 3-5 zone distincte (șterge o „clădire" prin petic de culoare uniformă, mută/adaugă un obiect, schimbă o zonă de „vegetație"). Notează coordonatele fiecărei modificări într-un `truth.geojson` cu poligoane, un `id` și o descriere scurtă per zonă.

**Check**:
```
python -c "import json; d = json.load(open('data/reference/truth.geojson')); print(len(d['features']), 'zone modificate')"
```

**Terminat când**: `truth.geojson` are între 3 și 5 features, fiecare cu geometrie validă, și `after.tif` are exact aceleași dimensiuni/CRS ca `before.tif`.

**Rollback**: `rm data/reference/after.tif data/reference/truth.geojson`

**Notă**: `truth.geojson` nu intră niciodată în antrenarea modelului (doar în evaluarea din T-05) — dacă adevărul se scurge în antrenare, recall-ul măsurat nu mai înseamnă nimic.

---

## T-04 — Features per patch

**Obiectiv**: `app/backend/features.py` cu o funcție care, dat un raster, întoarce un array de features per patch.

**Fă**: împarte rasterul în patch-uri (implicit 32×32 px, parametru reglabil). Per patch: culoare medie (per bandă), varianță locală, gradient (Sobel sau echivalent). Fără buclă Python peste patch-uri — reshape în blocuri + reduceri numpy pe axe.

**Check**:
```
python -c "
import time, rasterio
from app.backend.features import extract_features
d = rasterio.open('data/reference/before.tif')
t = time.perf_counter()
f = extract_features(d.read(), patch=32)
print(f.shape, f'{time.perf_counter()-t:.2f}s')
"
```

**Terminat când**: rulează sub 10s pe `before.tif` și forma array-ului e `(n_patches, n_features)`.

**Rollback**: `rm app/backend/features.py`

---

## T-05 — Detecție cu Isolation Forest

**Obiectiv**: `app/backend/detect.py` — antrenează pe features din `before.tif`, scorează `after.tif`, întoarce GeoJSON cu poligoanele anormale + scor.

**Fă**: `IsolationForest` din scikit-learn, `max_samples` rezonabil (nu tot setul). Antrenează pe patch-urile din `before.tif`, scorează patch-urile din `after.tif`, mapează scorurile înapoi la coordonate geografice, produce poligoane pentru top-N patch-uri anormale.

**Check**:
```
python -c "
import json, time
from app.backend.detect import detect_changes
t = time.perf_counter()
result = detect_changes('data/reference/before.tif', 'data/reference/after.tif')
truth = json.load(open('data/reference/truth.geojson'))
# recall: cate din zonele din truth apar in top-20 candidati din result
print(f'{time.perf_counter()-t:.2f}s', len(result['features']), 'candidati')
"
```
Recall-ul exact (câte din zonele `truth.geojson` apar în top-20 candidați) se calculează manual sau într-un script separat de evaluare — cifra intră în [[Jurnal]], nu doar timpul.

**Terminat când**: rulează sub 30s (train + score) și recall-ul pe perechea sintetică e măsurat și scris în jurnal — nu e nevoie de un prag minim la primul run, dar cifra trebuie să existe.

**Rollback**: `rm app/backend/detect.py`

**Atenție**: pragul de sensibilitate e parametru, nu constantă în cod. Dacă recall-ul iese slab, se ajustează pragul/dimensiunea patch-ului și se renotează — nu se ascunde cifra proastă.

---

## T-06 — Tiling și servire

**Obiectiv**: rasterul se servește pe ferestre (COG + range request), nu integral, cu latență mică per tile.

**Fă**: convertește `before.tif`/`after.tif` în COG (`rio cogeo create`). Servire prin `titiler` sau echivalent, lipit de backend-ul din T-07 (poate fi făcut în paralel, dar testat abia după T-07 există).

**Check**:
```
python -c "
import time, requests
t = time.perf_counter()
r = requests.get('http://localhost:8000/tiles/before/10/512/512.png')
print(r.status_code, f'{(time.perf_counter()-t)*1000:.0f}ms')
"
```

**Terminat când**: latența per tile e sub 150ms local și status code e 200.

**Rollback**: `rm data/reference/*.cog.tif`, revert config titiler

---

## T-07 — Backend minim

**Obiectiv**: FastAPI cu endpoint-uri pentru upload, status, rezultate — job-ul de detecție rulează async.

**Fă**: `app/backend/main.py` cu `BackgroundTasks` (nu Celery/Redis — vezi [[Decizii]]). Endpoint-uri: `POST /flights` (upload), `POST /flights/{id}/process`, `GET /flights/{id}/status`, `GET /flights/{id}/result`. SQLite pentru metadata, cu `PRAGMA journal_mode=WAL`.

**Check**:
```
uvicorn app.backend.main:app --port 8000 &
python -c "
import requests, time
r = requests.post('http://localhost:8000/flights/test/process')
for _ in range(30):
    s = requests.get('http://localhost:8000/flights/test/status').json()
    if s['status'] == 'done': break
    time.sleep(1)
print(s)
"
```

**Terminat când**: un job pornit prin API ajunge la `status: done` fără să blocheze alte cereri în timpul procesării.

**Rollback**: `rm app/backend/main.py app/backend/*.db`

---

## T-08 — Frontend cu slider before/after

**Obiectiv**: React/Vite + MapLibre GL, hartă cu ortofotoplan + overlay de anomalii + slider before/after.

**Fă**: layer de raster (tile-urile din T-06) + layer GeoJSON (rezultatul din T-05, servit de T-07). Sliderul modifică `raster-opacity` pe un layer deja încărcat — nu schimbă sursa (altfel fiecare mișcare declanșează cereri de rețea).

**Check**: manual — încarci pagina, muți sliderul, confirmi vizual că nu apar cereri de rețea noi în timpul mișcării (tab Network din DevTools, filtrat pe timpul cât se mișcă sliderul).

**Terminat când**: harta afișează corect poligoanele peste raster, iar sliderul e fluid, fără reîncărcare de sursă.

**Rollback**: `rm -rf app/frontend/src/components/Slider*`

---

## Ce raportează la final

Pentru verificarea finală: ce task-uri au trecut (cu output-ul checkurilor), cifrele măsurate (recall T-05, timpii T-04/T-05/T-06), ce s-a blocat și la ce pas, orice decizie ad-hoc luată în timpul execuției care nu era deja în [[Decizii]] — astea sunt exact punctele de verificat, nu de presupus că sunt corecte.
