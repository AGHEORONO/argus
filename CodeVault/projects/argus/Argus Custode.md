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

## Stare curentă (2026-08-30)

**Funcțional și livrat**, în două forme din aceeași bază de cod:

- **Web, public**: backend pe Render, frontend pe Vercel — ambele verificate independent din afara
  sesiunii, nu doar prin status API.
- **Aplicație Windows de sine stătătoare**: `.uild-desktop.ps1` produce un `.exe` cu fereastră
  proprie peste WebView2.

Detecția atinge **recall 4/4** pe adevărul sintetic de referință, măsurat automat în CI la fiecare
push. 90 de teste pytest și 48 Playwright.

**Ce rămâne**: nimic n-a atins vreodată o poză reală de dronă — EXIF-ul din teste e scris de noi.
Faza 2 (fotogrammetrie cu OpenDroneMap) e blocată de [[Intrebari deschise]] Î-05 și de hardware.
Lista completă a limitelor: [[Prezentare generala]], secțiunea 10.

## Navigare

**Pentru caietul de practică**, cele două note de sinteză:

- [[Prezentare generala]] — ce face, cum e construit, ce funcționează măsurat, ce nu s-a făcut
- [[Probleme si rezolvari]] — fiecare problemă întâlnită, cu cauza și reparația
- [[Verificare cu cititor de ecran]] — scenariul de parcurs cu NVDA, singura verificare
  de accesibilitate care nu se poate automatiza

Restul:

- [[Task-uri de start]] — T-01…T-08, de aici se lucrează zilnic
- [[De facut]] — ce a rămas neterminat, de reluat
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
| Tiling | COG + tiling propriu (rasterio + Pillow) | **da** |
| Detecție anomalii | Isolation Forest (scikit-learn) | nu |
| Backend | FastAPI + SQLite | nu |
| Frontend | React/Vite + MapLibre GL | nu |

*Actualizare 2026-08-30*: tiling-ul nu s-a făcut cu titiler sau gdal2tiles, ci cu un modul propriu
care generează tile-uri XYZ la cerere din COG, cu cache de dataset — vezi [[Decizii]] D-012.
Fotogrammetria rămâne singura bucată neîncepută. S-a adăugat, neplanificat, împachetarea ca
aplicație Windows (PyInstaller + WebView2).

Singurele bucăți cu adevărat noi sunt fotogrammetria și tiling-ul. Detecția de anomalii, care e partea „de efect", e adaptarea unui algoritm pe care l-ai rulat deja — se schimbă unitatea spațială (patch de dronă în loc de pixel satelitar), nu metoda.
