---
tags: [argus, proiect, practica, hub]
created: 2026-08-17
type: hub
---

# Argus Custode

Nota hub a proiectului. Tot ce ține de Argus pleacă de aici.

## Ce face

Zbori cu drona peste aceeași zonă la momente diferite. Aplicația generează ortofotoplanul fiecărui zbor, le aliniază, și marchează pe hartă zonele care s-au schimbat între ele — cu un scor de anomalie, nu doar o diferență brută de pixeli.

Nume scurt în cod, comenzi și repo: `argus`. Numele complet, pentru prezentare și documentație: **Argus Custode** — Argus, gigantul cu o sută de ochi care nu doarme niciodată; *custode*, cuvânt identic în română și italiană, cel care are ceva în grijă.

## Stare curentă

Planificare. Zero cod, zero date de zbor, hardware de procesare încă necunoscut. Vezi [[Intrebari deschise]].

## Navigare

- [[Task-uri de start]] — T-01…T-08, de aici se lucrează zilnic
- [[Plan de implementare]] — cele 7 faze, ordinea reală de execuție, MVP vs. stretch
- [[Intrebari deschise]] — necunoscutele și ce fază blochează fiecare
- [[Decizii]] — deciziile luate, cu motivul
- [[Jurnal]] — jurnal de lucru pe zile

## Stack

Reutilizează aproape integral stack-ul de la Nereus, ceea ce înseamnă că partea de risc tehnic nou e mică:

| Strat | Unealtă | Nou față de Nereus? |
|---|---|---|
| Fotogrammetrie | OpenDroneMap în Docker | **da** |
| Raster / reproiecție | GDAL | parțial |
| Tiling | titiler sau gdal2tiles | **da** |
| Detecție anomalii | Isolation Forest (scikit-learn) | nu |
| Backend | FastAPI + SQLite | nu |
| Frontend | React/Vite + MapLibre GL | nu |

Singurele bucăți cu adevărat noi sunt fotogrammetria și tiling-ul. Detecția de anomalii, care e partea „de efect", e adaptarea unui algoritm pe care l-ai rulat deja — se schimbă unitatea spațială (patch de dronă în loc de pixel satelitar), nu metoda.
