---
tags: [argus, practica, prezentare, caiet]
created: 2026-08-30
type: referinta
---

# Prezentare generală — ce este și ce s-a construit

Proiect: [[Argus Custode]]. Notă scrisă pentru **caietul de practică**: ce face aplicația, cum e
construită, ce funcționează măsurat, și ce nu s-a făcut.

Perechea ei este [[Probleme si rezolvari]], care documentează defectele întâlnite pe drum.

---

## 1. Problema pe care o rezolvă

O firmă de topografie zboară cu drona peste același sit la intervale de timp — lunar, de exemplu, pe
un șantier sau o carieră. Rezultatul fiecărui zbor este un **ortofotoplan**: o imagine aeriană
corectată geometric, cu coordonate reale.

Întrebarea practică este *„ce s-a schimbat din martie până acum?"*. Răspunsul se dă azi prin
comparație vizuală, ochi pe ecran, ceea ce e lent și depinde de atenția operatorului.

Argus Custode primește două zboruri ale aceluiași sit și **marchează pe hartă zonele care s-au
schimbat**, ordonate după un scor de anomalie — nu o diferență brută de pixeli, care ar semnala
fiecare umbră și fiecare mașină mutată.

Numele: Argus, gigantul cu o sută de ochi care nu doarme; *custode*, cuvânt identic în română și
italiană, cel care are ceva în grijă. Vezi [[Decizii]] D-001.

---

## 2. Cum funcționează detecția

Metoda este **Isolation Forest pe trăsături de diferență**. Ideea centrală, care a fost și
descoperirea care a făcut proiectul să funcționeze:

1. Imaginea se împarte în pătrate de 32×32 px (*patch*-uri).
2. Pentru fiecare patch se extrag 12 trăsături: culoare medie, varianță locală și gradienți
   spațiali, pe fiecare din cele trei canale.
3. Se calculează **diferența absolută** între trăsăturile aceluiași patch în cele două zboruri:
   `X_diff = |X_after - X_before|`.
4. Isolation Forest învață ce înseamnă „normal" pe `X_diff`. Cum peste 99% din scenă nu se schimbă,
   distribuția normală este *lipsa schimbării*, iar zonele modificate ies ca anomalii.

**De ce contează pasul 3**, măsurat în [[Jurnal]] (T-05, 17 august):

| Abordare | Recall la top-20 | Recall la top-50 |
|---|---|---|
| Trăsături absolute, doar `before` | 0/4 | 0/4 (4/4 abia la top-3000) |
| **Trăsături de diferență (`X_diff`)** | **3/4** | **4/4** |

Modelul antrenat doar pe `before` separă anomaliile *naturale* de textură și relief ale scenei — o
stâncă e la fel de „anormală" ca o clădire demolată. Diferența temporală e întrebarea corectă.

---

## 3. Cum se măsoară calitatea

Nu prin apreciere vizuală. Vezi [[Decizii]] D-013.

Se pornește de la un ortofotoplan public real (OpenAerialMap, Rumicucho Ruins, licență CC-BY) și se
generează programatic o pereche `after` cu **patru schimbări injectate la coordonate cunoscute**:
o structură demolată, un obiect nou apărut, vegetație îndepărtată, un șanț de excavație. Adevărul
de referință se scrie în `truth.geojson`.

Calitatea = **câte din cele patru zone cunoscute apar în primii N candidați**.

Rezultat curent, rulat automat în CI la fiecare push:

```
recall benchmark (seed 20260826, top_n=50)
  structura demolata       rang 10
  obiect nou aparut        rang  1
  vegetatie indepartata    rang  9
  sant de excavatie        rang  2
  recall 4/4, adancime maxima 10
  precizie 18/18 candidati pe o schimbare reala (100%)
```

**„Adâncimea maximă" nu e decorativă**: recall-ul singur e trivial de păcălit — un detector care
colorează tot situl scoate 4 din 4. Rangul celei mai adânc găsite schimbări costă nimic și face
cifra onestă.

**Limita, spusă cinstit**: cifra măsoară doar tipurile de schimbare injectate de noi. E o limită
inferioară utilă, nu o validare pe date reale de zbor.

---

## 4. Arhitectura

| Strat | Tehnologie | Fișier principal |
|---|---|---|
| Detecție anomalii | scikit-learn, Isolation Forest | `app/backend/detect.py` |
| Trăsături per patch | NumPy vectorizat, fără bucle Python | `app/backend/features.py` |
| Servire hărți | COG + tiling dinamic, Pillow, cache de dataset | `app/backend/tiles.py` |
| Model de date | SQLite (WAL), situri / capturi / comparații | `app/backend/sites.py` |
| API | FastAPI, `BackgroundTasks` | `app/backend/main.py` |
| Ingestie foto | EXIF, XMP, blur, GPS, suprapunere | `app/backend/ingest.py` |
| Auto-seed demo | descărcare + generare la pornire | `app/backend/provision.py` |
| Rădăcină de date | un singur loc care decide unde se scrie | `app/backend/paths.py` |
| Interfață | React + Vite + MapLibre GL | `app/frontend/src/App.jsx` |
| Aplicație desktop | uvicorn în fir + WebView2 | `desktop/argus_desktop.py` |

### Modelul de date

**Sit** (loc monitorizat) → **capturi** (o imagine, o dată) → **comparații** (detecție între oricare
două capturi ale aceluiași sit).

Modelul inițial făcea ca un „zbor" să însemne o **pereche** de rastere, deci comparația era fixată la
încărcare. O firmă zboară același sit lunar și vrea progresia, nu un singur salt — perechea era
unitatea greșită. Vezi [[Decizii]] D-018.

Baza de referință este **întotdeauna** captura mai veche, indiferent de ordinea argumentelor.
Altfel aceeași pereche s-ar putea stoca de două ori cu sensuri opuse, iar „ce s-a schimbat din
martie" ar depinde de ce câmp a completat utilizatorul primul.

### Decizii tehnice care merită menționate

- **COG cu tiling dinamic**, nu piramidă de PNG-uri pe disc. Un singur fișier acoperă toate
  nivelurile de zoom; pre-tiling-ul ar însemna mii de fișiere mici. Vezi [[Decizii]] D-012.
- **Fără Celery, Redis sau PostGIS.** `BackgroundTasks` și SQLite sunt suficiente la volumul unui
  proiect de practică; restul ar fi servicii de întreținut pentru zero câștig măsurat.
  Vezi [[Decizii]] D-007.
- **Suprapunerea se estimează din GPS și footprint**, nu prin potrivire de trăsături între imagini —
  care ar costa secunde per pereche și ar transforma o validare „de cinci secunde la intrare" exact
  în lucrul pe care trebuie să-l evite. Vezi [[Decizii]] D-016.

---

## 5. API

21 de rute. Cele care contează:

**Situri și comparații** (modelul curent)
```
POST /sites                              creează un sit
GET  /sites                              listă, cu număr de capturi și interval
POST /sites/{id}/captures                încarcă o captură datată
GET  /sites/{id}/captures                capturile unui sit, cronologic
POST /sites/{id}/comparisons             compară oricare două capturi
GET  /comparisons/{id}                   rezultatul, ca GeoJSON
```

**Zboruri** (modelul inițial, păstrat pentru demo)
```
POST /flights                            încarcă o pereche before/after
POST /flights/{id}/process               pornește detecția asincron
GET  /flights/{id}/status                pending | running | done | failed
GET  /flights/{id}/result                GeoJSON, sau 202 cât timp rulează
```

**Ingestie de fotografii**
```
POST /flights/{id}/photos                încarcă pozele brute
POST /flights/{id}/validate              verifică blur, GPS, suprapunere
GET  /flights/{id}/validation             raportul persistat
```

**Hărți**
```
GET /tiles/{layer}/{z}/{x}/{y}.png                        demo
GET /tiles/flights/{id}/{layer}/{z}/{x}/{y}.png           per zbor
GET /tiles/sites/{id}/{capture}/{z}/{x}/{y}.png           per captură
```

---

## 6. Interfața

Layout în stil unealtă tehnică, nu pagină de prezentare: o bară de activități verticală cu trei
destinații (Ingestie, Comparație, Anomalii), un panou de unelte, și harta ca vizor propriu.

**Ce se poate face**: alegi două zboruri dintr-o riglă de timp proporțională cu timpul scurs, apeși
compară, iar anomaliile apar pe hartă. Sliderul de amestec trece continuu între zborul de referință
și cel comparat. Schimbările cunoscute de referință se pot suprapune, ca demo-ul să spună explicit
ce *ar trebui* găsit — răspuns direct la observația „nu-mi dau seama ce ar trebui să fie anomaliile".

### Accesibilitatea, tratată ca cerință, nu ca finisaj

Aceasta a fost zona cu cel mai mult efort și cu cele mai multe defecte găsite — detaliile complete
sunt în [[Probleme si rezolvari]], secțiunea 5.

Ce e implementat:

- **Echivalent textual complet pentru hartă.** Poziția fiecărei anomalii e disponibilă în cuvinte:
  zonă numită, coordonate rostite, suprafață, și dacă se suprapune cu o schimbare cunoscută. Fără
  asta, rezultatul central al aplicației ar fi fost exclusiv vizual.
- **Un singur tab stop** pentru raftul de unelte (roving tabindex), în loc de vreo cincisprezece
  opriri. Săgețile schimbă panoul fără Enter.
- **Dialog nativ `<dialog>`** pentru lista completă, ceea ce aduce capcană de focus, `Escape` și
  `inert` pe fundal — inclusiv peste DOM-ul injectat de MapLibre, pe care altfel l-am fi uitat.
- **Reflow verificat la 320 px** — echivalentul a 400% zoom pe un ecran de 1280.
- **Anunțuri** pentru operațiile care altfel n-ar avea efect perceptibil non-vizual.
- **Contraste măsurate**, nu apreciate din ochi.
- **Ținte de minimum 24×24 px** (WCAG 2.2 SC 2.5.8); bara de activități e 88×64, deci trece și
  pragul AAA de 44 px.

Alegerea WebView2 pentru aplicația desktop a fost făcută tocmai ca să nu se piardă nimic din asta:
fiind Chromium, cititoarele de ecran se comportă identic cu browserul.

---

## 7. Cum se livrează

Aceeași bază de cod, două forme.

### Web (public, live)

- **Backend**: `https://argus-backend-yw3h.onrender.com` — Render, tier gratuit, Docker.
- **Frontend**: `https://argus-agheoronos-projects.vercel.app` — Vercel.

Ambele verificate independent din afara sesiunii, cu `curl`, nu doar prin status API.

Backendul se auto-seedează la pornire, fiindcă discul e efemer pe tier-ul gratuit: descarcă
ortofotoplanul de referință dacă lipsește, generează perechea sintetică, construiește COG-urile și
rulează detecția demo. Vezi [[Decizii]] D-008.

### Aplicație Windows de sine stătătoare

```powershell
.\build-desktop.ps1
```

Produce un folder cu `.exe` și o arhivă `.zip` (~302 MB). Backendul pornește pe un port local ales
la rulare și servește și interfața **din aceeași origine**, deci nu există CORS. Fereastra e
WebView2 (Edge), preinstalat pe Windows 11.

Datele stau în `%LOCALAPPDATA%\Argus`, împreună cu `argus-desktop.log`.

Măsurat: pornire ~2 s cu datele deja prezente; 13–33 s la prima pornire pe un calculator gol, unde
se descarcă 16 MB și se construiesc COG-urile.

**Limită**: executabilul e nesemnat, deci prima rulare arată un avertisment SmartScreen. Semnarea
costă bani și nu s-a făcut.

---

## 8. Testare și verificare automată

Aceasta este partea în care s-a investit cel mai mult după ce s-a văzut cât de ușor trece un defect
printr-un test verde.

| Suită | Câte | Ce acoperă |
|---|---|---|
| `pytest tests/` | **90** | detecție, tiling, ingestie, securitate, timeline, contract API, launcher desktop, pachetul construit |
| `playwright tests-e2e/` | **48** | tastatură, focus, dialog, reflow, echivalent textual, axe-core |

Rulate în CI la fiecare push, plus un pas separat care **verifică în ieșire** că benchmark-ul de
recall chiar a raportat 4/4 — un test sărit arată verde exact ca unul care trece, iar proiectul
livrase deja un server de tile-uri complet gol exact așa.

Câteva teste merită menționate individual, fiindcă verifică lucruri pe care un test obișnuit le-ar
rata:

- **`test_desktop_bundle.py`** pornește **executabilul construit** și îi cere un **tile** — nu
  pagina de start. O pagină servită dovedește doar că serverul pornește; un tile trece prin
  `rasterio`, DLL-urile de GDAL și `proj.db`, adică exact partea care lipsește dintr-un pachet
  prost făcut și care nu se vede la build.
- **`test_api_contract.py`** ține backendul simulat din testele de interfață lipit de cel real: cere
  API-ului adevărat să producă exact cheile folosite în simulare și pică dacă vreuna dispare.
- **`test_fara_cai_de_date_relative_in_backend`** scanează textul sursei și pică pe orice cale de
  date relativă. Verificată prin reintroducerea defectului pe care trebuie să-l prindă.
- **T-08** (drag-ul sliderului nu are voie să ceară tile-uri) — regresie găsită manual, devenită
  permanentă.

---

## 9. Cifre

```
59 de commituri
7.111 linii de cod de aplicație
  2.560  backend Python
  2.630  frontend JavaScript / JSX
  1.679  CSS
    242  launcher desktop
2.999 linii de teste
  2.206  pytest
    793  Playwright
21 de rute de API
```

---

## 10. Ce NU s-a făcut

Secțiune la fel de importantă ca restul.

- **Nimic n-a atins vreodată o poză reală de dronă.** EXIF-ul și XMP-ul din teste sunt scrise de noi,
  deci codul e validat împotriva propriilor presupuneri. Primul lucru de verificat când apar date de
  zbor. Vezi [[Decizii]] D-016.
- **Faza 2, fotogrammetria cu OpenDroneMap**, nu e implementată — blocată de
  [[Intrebari deschise]] Î-05 (clarificarea licenței AGPL) și de hardware.
- **Nicio trecere cu un cititor de ecran real** (NVDA, VoiceOver). Scanarea automată prinde în jur de
  o treime din problemele WCAG și niciuna dintre cele de ordine și sens.
- **Fără storage persistent extern.** Pe date reale ar fi obligatoriu S3/R2 pentru rastere și
  PostgreSQL/PostGIS pentru metadate. Vezi [[Decizii]] D-008.
- **Fără autentificare.** Backendul public e deschis, ceea ce e acceptabil pentru date sintetice
  publice, dar nu pentru date reale ale firmei. Vezi [[Decizii]] D-011.
- **Executabilul nu e semnat digital.**

---

## 11. Cum se pornește

**Local, din sursă** — dintr-un terminal propriu, nu dintr-o sesiune de agent (procesele pornite de
un agent se opresc odată cu ea):

```powershell
.\start-local.ps1          # backend + frontend pe http://127.0.0.1:4173
```

**Testele**:

```powershell
.venv\Scripts\python.exe -m pytest tests\ -q
cd app\frontend; npm run test:e2e
```

**Aplicația Windows**:

```powershell
.\build-desktop.ps1
```

---

Legături: [[Argus Custode]] · [[Probleme si rezolvari]] · [[Plan de implementare]] · [[Decizii]] ·
[[Jurnal]] · [[De facut]] · [[Intrebari deschise]]
