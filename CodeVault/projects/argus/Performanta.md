---
tags: [argus, performanta, arhitectura]
created: 2026-08-17
type: nota-tehnica
---

# Performanță

Proiect: [[Argus Custode]]. Cerință explicită: să fie rapid, nu doar corect. Deciziile de mai jos sunt luate acum pentru că sunt **ieftine la început și scumpe după** — schimbarea formatului de stocare sau a modului de citire, după ce ai construit peste ele, înseamnă rescriere.

Cifrele de mai jos sunt **ținte, nu măsurători**. Se înlocuiesc cu valori reale pe măsură ce taskurile din [[Task-uri de start]] le produc.

## Buget

| Operație | Țintă | Se măsoară în |
|---|---|---|
| Features pe raster de test | < 10 s | T-04 |
| Detecție completă (train + score) | < 30 s | T-05 |
| Latență per tile, local | < 150 ms | T-06 |
| Slider before/after | fără reîncărcare de sursă | T-08 |

## Deciziile care contează

### COG în loc de pre-tiling

Un ortofotoplan de dronă are sute de MB până la GB. Varianta clasică e să-l tai în mii de fișiere PNG înainte să-l servești. Varianta bună e Cloud Optimized GeoTIFF: un singur fișier, cu tile-uri interne și piramide de rezoluție, din care serverul citește prin range request exact bucata cerută.

De ce contează: pre-tiling-ul înseamnă un pas de procesare de minute după fiecare zbor, plus mii de fișiere de gestionat, plus spațiu duplicat. COG-ul elimină pasul întreg. La comercializare, diferența e între „procesare grea la fiecare upload" și „upload, gata".

### Fără bucle Python peste patch-uri

Un raster de 10.000×10.000 la patch de 32 px înseamnă ~97.000 de patch-uri. O buclă Python peste ele, cu câteva operații fiecare, e ordine de mărime mai lentă decât aceeași treabă făcută prin reshape în blocuri și reduceri pe axe în numpy.

Regula concretă din [[Task-uri de start]]: `arr.reshape(h//p, p, w//p, p)` și reduci pe axele blocurilor. Dacă în `features.py` apare `for` peste patch-uri, e greșit.

### Citire pe ferestre, nu integral

`rasterio` citește ferestre. Un raster de 4 GB nu se încarcă în RAM ca să calculezi media pe blocuri de 32 px. Contează mai ales pe hardware modest — și hardware-ul e încă necunoscut, vezi [[Intrebari deschise]].

### Antrenare pe subeșantion

Isolation Forest nu are nevoie de toate cele 97.000 de patch-uri ca să învețe distribuția normală a unei zone. `max_samples` rezonabil taie timpul de antrenare fără pierdere reală de calitate. E un parametru, deci se poate măsura diferența, nu se ghicește.

### SQLite cu WAL

O linie de configurare. Fără ea, un job care scrie blochează cititorii, iar interfața pare înghețată exact când utilizatorul se uită la ea. Cu ea, cititorii merg în paralel cu scriitorul.

### Sliderul nu reîncarcă nimic

În T-08, sliderul before/after modifică `raster-opacity` pe un layer deja încărcat. Dacă schimbă sursa hărții, fiecare mișcare declanșează cereri de rețea și demo-ul se bâlbâie fix în momentul în care se uită juriul.

## Ce **nu** optimizăm acum

Fără cache distribuit, fără GPU, fără paralelizare pe procese, fără rescriere în Rust. Toate au sens doar după ce există o măsurătoare care arată unde se duce timpul. Buget măsurat întâi, optimizare după — altfel optimizezi partea greșită și pierzi timpul de practică pe ea.
