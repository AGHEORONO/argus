---
tags: [argus, jurnal]
created: 2026-08-17
type: jurnal
---

# Jurnal de lucru

Proiect: [[Argus Custode]]. Intrare nouă sus. Scurt: ce s-a făcut, ce s-a blocat, ce urmează. Fără proză.

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
