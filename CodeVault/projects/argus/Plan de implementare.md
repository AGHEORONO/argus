---
tags: [argus, plan]
created: 2026-08-17
type: plan
---

# Plan de implementare

Proiect: [[Argus Custode]]. Plan provizoriu — cerințele oficiale de la firmă încă nu au venit, deci fazele sunt scrise ca bucăți independente, fiecare livrabilă separat. Când vin cerințele, se taie sau se reordonează faze, nu se rescrie planul.

## Constrângeri reale

| Constrângere | Stare |
|---|---|
| Timp | ~1 lună calendaristică, ritm intens |
| Hardware pentru fotogrammetrie | **necunoscut** — vezi [[Intrebari deschise]] |
| Date de zbor | **zero** la momentul scrierii |
| Cerințe oficiale | nu au venit încă |

Două dintre cele patru sunt necunoscute care ating exact aceeași fază: faza 2. Asta dictează ordinea de mai jos.

## Ordinea de execuție ≠ ordinea pipeline-ului

Reflexul e să construiești în ordinea în care curg datele: poze → ortofotoplan → tile-uri → detecție → hartă. Cu zero date și hardware necunoscut, ordinea asta te blochează în ziua unu, pe faza cu cel mai mare risc și cea mai mică valoare demonstrabilă.

Deci construim invers: **întâi bucata care nu depinde de nimic necunoscut și care e cea mai vizibilă** — detecția de schimbări plus harta, pe un ortofotoplan public descărcat. Fotogrammetria proprie vine la final, când se știe pe ce rulează, și dacă nu se poate rula, aplicația e deja funcțională pe rastere gata-făcute.

Ordine de atac: **4 → 6 → 5 → 3 → 1 → 2 → 7**.

Ce câștigi: după primele zile ai deja ceva demonstrabil pe ecran. Ce pierzi: nimic — fazele rămân aceleași, doar ordinea diferă.

Trucul pentru „zero date": nu ai nevoie de două zboruri reale ca să dezvolți faza 4. Iei un singur ortofotoplan public, îl duplici, și injectezi tu schimbări în copie (ștergi o clădire, muți un obiect, schimbi o zonă de vegetație). Acum ai o pereche before/after cu **adevăr cunoscut** — știi exact unde ai modificat, deci poți măsura dacă algoritmul găsește exact acolo. Cu date reale n-ai avea luxul ăsta: nimeni nu-ți spune unde e schimbarea. Ține setul sintetic și după ce vin datele reale, ca test de regresie.

## Fazele

### Faza 4 — Detecție de schimbări *(începe aici)*

Inima proiectului și singura parte care te diferențiază.

- **Intrare**: două ortofotoplanuri georeferențiate ale aceleiași zone
- **Ieșire**: GeoJSON cu poligoane marcate + scor de anomalie
- **Pași**: co-registrare (verificare aliniere pixel-cu-pixel) → împărțire în patch-uri (32×32 px, de calibrat) → features per patch (culoare medie, varianță locală, gradient) → Isolation Forest antrenat pe distribuția zborului de referință → flag pe patch-urile anormale din zborul nou
- **Gata când**: pe perechea sintetică, zonele modificate de tine ies în top-N scoruri, iar restul hărții rămâne curat
- **Risc**: prag de sensibilitate — prea strict nu vede nimic, prea larg marchează umbre și diferențe de iluminare ca schimbări. Lasă pragul și dimensiunea patch-ului ca parametri reglabili, nu constante în cod.

### Faza 6 — Frontend și hartă

- React/Vite + MapLibre GL. Layer de ortofotoplan + overlay cu poligoanele de anomalie.
- Elementul demonstrabil: **slider before/after** peste aceeași zonă. Se înțelege instant, fără explicații.
- **Gata când**: încarci un GeoJSON și îl vezi corect poziționat peste raster, iar sliderul compară cele două zboruri fluid.

### Faza 5 — Backend

- FastAPI + SQLite pentru metadata (identic ca abordare cu Nereus).
- Endpoint-uri: upload zbor, pornire procesare, status job, rezultate, servire tile-uri.
- Procesarea e lungă → job asincron. `BackgroundTasks` e suficient la volumul ăsta.
- **Gata când**: pornești un job de la frontend, vezi statusul evoluând și primești rezultatul fără să blochezi interfața.
- Skipped: Celery + Redis, PostGIS. De adăugat doar dacă apare nevoia reală de query-uri spațiale sau de joburi paralele — altfel sunt două servicii în plus de întreținut pentru zero câștig la scara asta.

### Faza 3 — Tiling

- Ortofotoplanul e prea mare ca să-l trimiți întreg în browser. Tăiat în tile-uri XYZ cu gdal2tiles, sau servit dinamic cu titiler (FastAPI-based, se lipește direct de faza 5).
- **Gata când**: harta se mișcă fluid pe un raster de câteva sute de MB.

### Faza 1 — Ingestie și validare

- Organizare pe sesiuni de zbor, fiecare cu metadata proprie. Fără asta, faza 4 nu are ce compara cu ce.
- Validare înainte de procesare: blur (varianța Laplacianului), overlap suficient între poze consecutive, GPS valid în EXIF.
- **Gata când**: un set cu poze proaste e respins cu motiv clar, înainte să consume ore de procesare.
- De ce contează: fotogrammetria pe poze proaste eșuează după ore, nu instant. Validarea de 5 secunde la intrare îți salvează cicluri lungi de așteptare.

### Faza 2 — Fotogrammetrie *(opțională, ultima)*

- OpenDroneMap în Docker: structure-from-motion + ortorectificare + DSM, din poze cu GPS.
- **Intrare**: poze brute → **Ieșire**: `orthophoto.tif` + model de suprafață
- **Gata când**: un set demo ODM produce un ortofotoplan pe care faza 4 îl poate consuma direct.
- **Risc principal al proiectului**: durează de la minute la ore, cere CPU și RAM serioase. Nu rulează pe free tier.
- **Fallback dacă hardware-ul nu permite**: rămâi pe ortofotoplanuri gata-făcute și declari faza 2 explicit în afara scopului. Aplicația funcționează integral fără ea — asta e chiar motivul pentru care e ultima.

### Faza 7 — Deployment

- Frontend + API pe Render/Vercel, ca la Nereus.
- Job-ul ODM **nu** merge acolo. Fie mașină dedicată, fie rulare locală cu trimiterea doar a rezultatelor către API.
- **Gata când**: cineva deschide un link și vede demo-ul fără să instaleze nimic.

## MVP vs. stretch

**MVP** (ce trebuie să existe): fazele 4, 6, 5, 3 pe date publice + un set sintetic cu adevăr cunoscut. Asta e deja o aplicație completă și demonstrabilă.

**Stretch** (dacă rămâne timp și apar resurse): faza 1 pe date reale, faza 2 cu ODM, faza 7 public, PostGIS, job queue.

Linia de demarcație e trasată exact acolo unde încep dependențele externe: tot ce ține doar de tine e MVP, tot ce depinde de hardware, dronă sau firmă e stretch. Așa, o întârziere care nu ține de tine nu îți poate rupe livrabilul.

## Riscuri

| Risc | Impact | Ce facem |
|---|---|---|
| Hardware insuficient pentru ODM | faza 2 cade | e ultima și opțională; fallback pe rastere gata-făcute |
| Datele de zbor nu vin la timp | fazele 1-2 cad | dezvoltare pe date publice + set sintetic de la început |
| Cerințele oficiale schimbă direcția | reordonare | faze independente, fiecare livrabilă singură |
| Fals-pozitive din umbre și iluminare | demo slab | prag și dimensiune patch reglabile; comparație pe zboruri la ore similare |
