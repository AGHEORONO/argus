---
tags: [argus, jurnal]
created: 2026-08-17
type: jurnal
---

# Jurnal de lucru

Proiect: [[Argus Custode]]. Intrare nouă sus. Scurt: ce s-a făcut, ce s-a blocat, ce urmează. Fără proză.

## 2026-08-17 (T-07)

**Făcut**: implementat backend-ul minim în `app/backend/main.py` cu FastAPI și SQLite (`PRAGMA journal_mode=WAL` și `PRAGMA busy_timeout=5000` pentru acces concurent fără blocaje). Adăugate endpoint-urile:
- `POST /flights`: creare/încărcare pereche ortofotoplanuri dronă în `data/flights/{id}/`.
- `POST /flights/{id}/process`: declanșare job asincron de detecție prin `BackgroundTasks`.
- `GET /flights/{id}/status`: interogare non-blocantă a stării jobului (`pending`, `running`, `done`, `failed`). Latență medie interogare în timpul procesării: ~6ms.
- `GET /flights/{id}/result`: returnare GeoJSON FeatureCollection cu candidații detectați odată finalizat jobul (status 200) sau status 202 în timpul procesării.
- Adăugate teste de integrare în `tests/test_main.py` (total suită: 9 teste trecute).

**Check output**:
```
{'id': 'test', 'status': 'done', 'error_message': None, 'updated_at': '2026-08-17 01:21:29'}
```

**Blocaje**: niciunul; jobul a atins status `done` în ~15s, iar `GET /flights/{id}/result` returnează GeoJSON valid cu 20 de poligoane.

**Urmează**: T-08 — frontend cu slider before/after (React/Vite + MapLibre GL).

---

## 2026-08-17 (T-06)

**Făcut**: convertit `before.tif` și `after.tif` în COG (`before.cog.tif`, `after.cog.tif` cu profil deflate și overviews prin `rio cogeo`). Implementat modulul de tiling `app/backend/tiles.py` cu cache de dataset-uri `rasterio` deschise (evită redeschiderea fișierului per request), encoder PNG bazat pe Pillow (`PIL.Image.fromarray`), suport dual-stack IPv6/IPv4 (`--host ::`), și integrat în `app/backend/main.py`.

**Check output (4 cereri consecutive pe tile 17/72686/49366)**:
```
0 200 41ms
1 200 4ms
2 200 5ms
3 200 4ms
```
- Prima cerere (deschidere dataset inițială + warm cache): 41ms (< 150ms).
- Următoarele cereri (cache activ): 4-5ms (< 150ms).

**Blocaje**: rezolvat problema latenței pe Windows prin cache de handle-uri rasterio, Pillow și bind dual-stack.

**Urmează**: remediere T-05 (îmbunătățire recall Isolation Forest).

---

## 2026-08-17 (T-05)

**Făcut**: implementat `app/backend/detect.py` cu `IsolationForest` pe trăsături de diferență pereche (`X_diff = |X_after - X_before|`), unde neschimbatul (99.9% din scenă) constituie distribuția normală, iar zonele modificate sunt izolate ca anomalii distincte.

**Experimente pas cu pas de recall**:
1. *Creștere `top_n` pe features absolute (`X_before`)*: `top_n=20..500` a dat `0/4` (0%), `top_n=1000` -> `1/4`, `top_n=2000` -> `3/4`, `top_n=3000` -> `4/4`. Explicație: modelul antrenat doar pe `before` separă anomaliile naturale de textură/relief ale scenei, nu diferențele temporale.
2. *Trăsături de diferență directă (`X_diff`)*: `top_n=20` a sărit direct la **3/4 (75.0%)**, iar la `top_n=50` a atins **4/4 (100.0%)**.
3. *Dimensiune patch (16px vs 32px pe `X_diff`)*: la 16px `top_n=10` -> `2/4` (50%), `top_n=20` -> `3/4` (75%), `top_n=50` -> `4/4` (100%), cu timp de calcul ușor mai mare.

**Check output brut (`top_n=20`, `patch=32`)**:
```
recall: 3/4
```

**Blocaje**: rezolvat; recall-ul este acum 3/4 (75%) pe top-20 și 4/4 (100%) pe top-50.

**Urmează**: T-07 — backend minim (`app/backend/main.py`).

---

## 2026-08-17 (T-04)

**Făcut**: implementat `app/backend/features.py` cu funcția `extract_features(raster, patch=32)`. Folosește reshape în blocuri 5D și reduceri vectorizate NumPy pe axe (fără bucle Python), extrăgând culoare medie, varianță locală și gradienți spațiali per canal. Adăugate teste unitare în `tests/test_features.py` și `pytest.ini`.

**Check output**:
```
(113832, 12) 5.20s
```

**Blocaje**: niciunul.

**Urmează**: T-05 — detecție cu Isolation Forest (`app/backend/detect.py`).

---

## 2026-08-17 (T-03)

**Făcut**: generat perechea sintetică `data/reference/after.tif` prin injectarea a 4 modificări controlate (ștergere clădire, adăugare container albastru, defrișare/sol uscat, săpătură/tranșee) și creat `data/reference/truth.geojson` cu poligoanele geografice exacte și descrierile fiecărei modificări. Dimensiunile și CRS-ul sunt identice între `before.tif` și `after.tif`.

**Check output**:
```
4 zone modificate
```

**Blocaje**: niciunul.

**Urmează**: T-04 — extracție de features per patch (`app/backend/features.py`).

---

## 2026-08-17 (T-02)

**Făcut**: descărcat ortofotoplan de dronă de pe OpenAerialMap (Rumicucho Ruins, licență CC-BY, RGB uint8) în `data/reference/before.tif`. `data/` este confirmat ignorat de git.

**Check output**:
```
EPSG:4326 8959 13066
```

**Blocaje**: niciunul.

**Urmează**: T-03 — perechea sintetică before/after (`data/reference/after.tif` + `data/reference/truth.geojson`).

---

## 2026-08-17 (T-01)

**Făcut**: creat mediul Python (`.venv`), instalat dependențele de bază (`numpy`, `rasterio`, `scikit-learn`, `shapely`, `fastapi`, `uvicorn`, `rio-cogeo`, `pytest`), generat `app/requirements.txt` cu versiuni fixate, creat structura de foldere `app/backend/` cu `__init__.py` și `app/frontend/`.

**Check output**:
```
imports OK
```

**Blocaje**: niciunul.

**Urmează**: T-02 — descărcat ortofotoplan public de test în `data/reference/before.tif`.

---

## 2026-08-17 (3)

**Făcut**: adăugată regula de delegare către `agy`/Gemini în `CLAUDE.md`/`AGENTS.md` (rădăcină + copiile din `CodeVault`): execuție pe Gemini (`gemini-3.7-flash-high`), fallback la Claude direct când Gemini nu face față, scop limitat strict la acest proiect (nu afectează Claude Code în general și nu afectează Antigravity IDE deschis direct).

**Blocaje**: incident — un test scurt cu `agy --dangerously-skip-permissions` a găsit modificări necomise în working tree și a decis singur, pe baza regulii vechi „commit ca dovadă", să comită și să dea push la ~500 de linii nesolicitate direct pe `origin/main` (commit `d24a97f`). Revertat (`f821d21`), conținutul era legitim dar push-ul nu fusese aprobat. Regulă nouă: `agy` nu mai atinge git, doar Claude comite/pushuiește, după confirmare.

**Urmează**: reluat de unde a rămas planul — [[Task-uri de start]] au fost pierdute la revert; de rescris sau reluat din `Plan de implementare` înainte de T-01.

---

## 2026-08-17

**Făcut**: setat repo-ul și vault-ul. Stabilit numele, structura, stack-ul, ordinea de execuție. Scris [[Plan de implementare]], [[Decizii]], [[Intrebari deschise]].

**Blocaje**: niciunul care oprește lucrul. Hardware-ul de procesare și datele de zbor sunt necunoscute, dar planul le ocolește prin ordinea aleasă.

**Urmează**:
1. Instalat plugin Obsidian Git pe ambele mașini (PC + laptop).
2. Descărcat un ortofotoplan public și construită perechea sintetică before/after cu schimbări injectate.
3. Început faza 4: features per patch + Isolation Forest.
