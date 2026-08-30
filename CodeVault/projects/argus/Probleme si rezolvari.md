---
tags: [argus, practica, probleme, caiet]
created: 2026-08-30
type: referinta
---

# Probleme întâlnite și cum au fost rezolvate

Proiect: [[Argus Custode]]. Notă scrisă pentru **caietul de practică**: fiecare problemă reală
din proiect, cu simptomul, cauza, reparația și ce a rămas de învățat din ea.

Ordinea e pe teme, nu cronologică. Fiecare intrare are data, ca să poată fi găsită în [[Jurnal]].

Un lucru merită spus de la început, fiindcă e tiparul care se repetă în aproape toate secțiunile:
**cele mai multe defecte nu s-au văzut citind codul, ci rulându-l.** Iar o parte dintre ele au
trecut nedetectate tocmai pentru că exista un test care le acoperea — dar testul verifica altceva
decât credea autorul lui.

---

## 1. Infrastructură și deployment

### 1.1 Build eșuat pe Render — versiune de Python incompatibilă cu numpy (2026-08-21)

**Simptom**: `build_failed` la primul deploy pe Render, înainte ca aplicația să pornească măcar o dată.

**Cauză**: `Dockerfile` fixa `python:3.11-slim`, dar `app/requirements.txt` fusese generat cu
`pip freeze` de pe Python 3.12 local. `numpy==2.5.2` nu are wheel precompilat pentru 3.11, deci
pip încerca să-l compileze din sursă și cădea.

**Reparație**: `FROM python:3.12-slim`, aceeași versiune ca local.

**De reținut**: `pip freeze` capturează versiuni legate de interpretorul pe care a rulat. Un
`requirements.txt` fără versiunea de Python alături e o jumătate de specificație. Versiunea din
`Dockerfile` și cea din CI sunt acum ținute explicit egale, cu comentariu care spune de ce.

### 1.2 Memorie insuficientă la pornire — două runde (2026-08-21)

**Simptom**: `update_failed`, containerul murea cu **exit 137** (OOM killer) la pornire, după ce
build-ul trecuse. Limita pe tier-ul gratuit Render: 512 MB.

**Cauză, runda 1**: `generate_synthetic_pair()` și `detect_changes()` încărcau ortofotoplanul
întreg în memorie, de mai multe ori (~670 MB pe un raster de 8959×13066).

**Reparație, runda 1**: citire pe ferestre cu `rasterio.windows.Window`, în loc de tot rasterul
deodată.

**Ce s-a învățat din eșecul parțial**: OOM-ul a reapărut, dar **după 2 minute și 28 de secunde în
loc de 16 secunde**. Cifra asta a fost dovada că fixul chiar a ajutat, doar că insuficient — fără
ea, ar fi fost imposibil de spus dacă direcția era bună sau greșită.

**Cauză, runda 2**: chiar cu streaming, construirea celor două COG-uri plus antrenarea Isolation
Forest depășeau tot 512 MB la rezoluție aproape completă.

**Reparație finală**: `downsample_if_needed()` reduce rasterul la maximum 3000 px pe latura lungă,
prin citire decimată GDAL — nu materializează niciodată rezoluția completă în memorie. Zonele
sintetice de schimbare, care erau coordonate fixe calculate pentru 8959×13066, au trebuit scalate
proporțional; altfel ar fi căzut în afara imaginii la rezoluția redusă. Vezi [[Decizii]] D-010.

**De reținut**: un eșec care se mută în timp e o informație, nu o repetare. Și: o optimizare de
memorie poate invalida constante calculate pentru dimensiunea veche — au trebuit căutate toate.

### 1.3 Link public care cerea totuși autentificare (2026-08-21)

**Simptom**: frontendul era pe Vercel, dar linkul redirecta către login. Obiectivul fazei era
exact „cineva deschide un link, vede demo-ul, fără cont".

**Cauză**: Vercel activează implicit SSO protection pe **toate** deploy-urile unui proiect de tip
echipă (`ssoProtection.deploymentType: all_except_custom_domains`), inclusiv producția. Nu era o
setare greșită de-a noastră, ci un implicit al platformei.

**Reparație**: `vercel project protection disable argus --sso`, cerut și confirmat explicit de
utilizator înainte, fiind o schimbare de expunere publică. Verificat cu `curl` înainte (302 către
`vercel.com/sso-api`) și după (200 direct). Vezi [[Decizii]] D-011.

**De reținut**: „am făcut deploy" nu înseamnă „e accesibil". Verificarea trebuie făcută din afara
contului, nu din browserul în care ești logat.

### 1.4 Variabila de mediu care nu se propagă între medii (2026-08-21)

**Simptom**: build-ul de preview funcționa, cel de producție cerea de la adresa greșită.

**Cauză**: CLI-ul Vercel nu propagă automat variabilele între Production și Preview. `VITE_API_BASE`
trebuie adăugat separat în fiecare mediu.

**Reparație**: adăugat în ambele, și verificat **în bundle-ul construit** că adresa corectă chiar
apare, cu `vercel curl`, nu doar în panoul de setări.

**De reținut**: o variabilă de build se verifică în artefactul rezultat, nu în interfața care spune
că a fost setată.

### 1.5 Un URL raportat ca live, care nu exista (2026-08-17)

**Simptom**: în [[Jurnal]] fusese scris `https://argus-backend.onrender.com` ca „URL rezultat" al
Fazei 7.

**Cauză**: fișierele de configurare (`Dockerfile`, `render.yaml`, `vercel.json`) erau reale și
corecte, dar deployment-ul efectiv nu se întâmplase niciodată. Instrucțiunile de conectare fuseseră
scrise ca și cum ar fi fost deja executate.

**Reparație**: `curl` pe acel URL → timeout după 15 s (cod `000`). Intrarea din jurnal a fost
corectată explicit, nu ștearsă, iar Faza 7 a fost redeschisă.

**De reținut**: asta a dus direct la [[Decizii]] D-014 — nicio fază nu e declarată gata fără o
dovadă rulată, notată în jurnal. Este cea mai valoroasă regulă a proiectului și a prins ulterior
încă cel puțin cinci afirmații false.

### 1.6 Line endings diferite între mașini (2026-08-21)

**Simptom**: fișiere care apăreau modificate integral după un `git checkout` pe cealaltă mașină.

**Cauză**: lipsea `.gitattributes`, iar `core.autocrlf=true` pe Windows normaliza diferit la fiecare
checkout. Suspectul inițial — un BOM stricat pe `AGENTS.md`/`CLAUDE.md` — era intact la verificare.

**Reparație**: `.gitattributes` cu `* text=auto eol=lf` și rastere marcate explicit ca binare, plus
`git add --renormalize .` ca fixul să se aplice și retroactiv.

**De reținut**: primul suspect nu era cauza. Verificarea suspectului a costat un minut și a evitat o
reparație pe fișierul greșit.

---

## 2. Calitatea detecției

### 2.1 Recall raportat care nu s-a reprodus (2026-08-19)

**Simptom**: jurnalul din 17 august raporta recall 3/4 și 4/4. Pe mașina desktop, măsurat
independent, aceleași configurații dădeau **2/4** și **3/4**.

| Configurație | Raportat (17 aug) | Măsurat independent (19 aug) |
|---|---|---|
| `top_n=20`, `patch=32` | 3/4 | **2/4** |
| `top_n=50`, `patch=32` | 4/4 | **3/4** |

**Cauză parțială găsită**: `generate_synthetic_pair()` folosea `np.random.normal(...)` **fără seed
fixat** pentru zgomotul dintr-o zonă. La fiecare regenerare pe altă mașină, `after.tif` nu mai era
identic bit cu bit — deși planul declara explicit setul sintetic drept test de regresie stabil între
mașini.

**Reparație**: `np.random.default_rng(42)`.

**Ce a rămas neexplicat, spus cinstit**: seed-ul lipsă nu explică diferența la celelalte zone, care
sunt transformări deterministe. Rămâne o necunoscută reală — posibil versiuni diferite de
biblioteci, sau `before.tif` care nu e identic la byte (lipsește un hash salvat la descărcare).
Nu s-a săpat mai departe, dar s-a **notat ca necunoscut**, nu mascat.

**De reținut**: un „test de regresie" cu o sursă de aleator neseminată nu e un test de regresie.
Și: o cifră care nu se reproduce trebuie corectată în jurnal, nu ștearsă.

### 2.2 O zonă pe care detectorul n-o găsea deloc (2026-08-19 → 2026-08-21)

**Simptom**: zona „vegetație îndepărtată" nu apărea în primii 100+ candidați, pe nicio configurație.

**Analiză**: nu era o problemă de prag sau de `top_n` — creșterea lor doar adăuga zgomot. Părea o
limitare reală a trăsăturilor folosite (culoare medie, varianță, gradient) pentru schimbări de tip
vegetație/contrast. Documentată ca atare în [[Decizii]] D-009, **fără** a pretinde că e rezolvată.

**Rezolvare, neplanificată**: după reducerea rezoluției făcută pentru memorie (1.2), zona a devenit
detectabilă și recall-ul a urcat la **4/4**. Efect secundar, nu intenție. Explicația probabilă —
netezirea din resampling reduce zgomotul local care o ascundea — nu a fost investigată până la capăt
și e notată ca ipoteză, nu ca fapt.

**De reținut**: o reparație făcută pentru un motiv poate rezolva altceva. Merită verificat, dar nu
merită prezentat ca și cum ar fi fost planificat.

### 2.3 Detectorul nu putea spune „nimic nu s-a schimbat" (2026-08-26)

**Simptom**: pe două rastere identice, detectorul întorcea cinci anomalii cu scor 0,5.

**Cauză**: nu exista prag sub care un candidat să fie respins; funcția întorcea întotdeauna primii N
după scor, indiferent cât de mic era scorul.

**Reparație**: prag explicit, iar interfața arată acum starea „zero anomalii" ca rezultat valid, nu
ca eroare.

**De reținut**: un detector care nu poate întoarce mulțimea vidă nu răspunde la întrebare, ci doar
sortează.

---

## 3. Defecte de fond găsite la auditul cu ochi proaspeți (2026-08-26)

Un agent cu memorie curată, instruit **să nu creadă niciun comentariu și niciun mesaj de commit**,
a verificat opt afirmații ale proiectului. Trei erau false. Metoda merită reținută: a verifica
propriile afirmații e greu tocmai pentru că le cunoști justificarea.

### 3.1 Panoul de anomalii pictat permanent peste hartă

**Simptom**: în centrul ecranului, utilizatorul vedea o celulă de tabel. Panoul măsura 1440×675 px
peste hartă, permanent.

**Cauză**: `display: flex` pus pe `dialog.anomalies-sheet` suprascria regula implicită a browserului
`dialog:not([open]) { display: none }`. Dialogul era „închis" logic și vizibil fizic.

**De ce n-a prins testul**: testul verifica `dialog.open === false` — adevărat — și nu s-a uitat
niciodată dacă elementul e **vizibil**.

**Reparație**: regula CSS corectată, iar testul verifică acum `display` calculat, nu doar starea
logică. Testul de regresie există azi în `tests-e2e/dialog.spec.js`.

### 3.2 Testul algoritmului central trecea cu `after == before`

**Simptom**: niciunul — testul era verde.

**Cauză**: toate cele patru aserțiuni erau tautologice. `len(features) == 2` doar repeta parametrul
`top_n=2` dat la intrare. Testul ar fi trecut și dacă detecția n-ar fi făcut nimic.

**Reparație**: aserțiuni pe conținut, nu pe formă — că zonele cunoscute sunt regăsite, la ce rang.

**De reținut**: un test care nu poate să pice nu e un test. Regula folosită de atunci: **introdu
defectul intenționat și confirmă că testul îl prinde.** Aplicată din nou la garda de căi (9.4).

### 3.3 Niciun test nu verifica dacă un tile are pixeli

**Simptom**: serverul de tile-uri răspundea `HTTP 200` cu imagini complet goale.

**Cauză**: testele verificau codul de stare și tipul de conținut, niciodată conținutul.

**Reparație**: aserțiuni pe octeții PNG și pe dimensiunea minimă. Aceeași verificare e azi cea care
dovedește că aplicația împachetată chiar funcționează (9.3).

### 3.4 Tiling-ul nu reproiecta niciodată

**Simptom**: niciunul pe datele demo.

**Cauză**: codul compara limite exprimate **în grade** cu limite exprimate în CRS-ul nativ al
rasterului. Mergea doar fiindcă rasterul demo e din întâmplare EPSG:4326 — neobișnuit pentru un
ortofotoplan real.

**Impact evitat**: orice ieșire de OpenDroneMap sau Pix4D (tipic UTM) ar fi servit tile-uri goale
cu `HTTP 200` și `has_tiles: true`. Adică primul ortofotoplan real al firmei ar fi eșuat **tăcut**.

**De reținut**: o coincidență în datele de test poate ascunde o eroare de fond. Merită întrebat
explicit „ce e special la datele mele de test?".

### 3.5 Coordonate în CRS-ul sursei, ajunse în text citit cu voce tare

**Simptom**: panoul accesibil anunța *„la aproximativ 544820807340 de metri de centru"*.

**Cauză**: detecția emitea coordonate în CRS-ul sursei, nereproiectate.

**Capcana**: rezumatul de deasupra părea plauzibil, fiindcă venea din **altă cale de cod** care
reproiecta corect. Două căi pentru aceeași informație, una greșită.

### 3.6 COG-urile nu se reconstruiau niciodată

**Simptom**: după o corecție de imagini, se vedea rasterul vechi cu anomaliile noi peste, iar starea
raportată era `done`.

**Cauză**: COG-ul se construia doar dacă lipsea, nu și dacă sursa era mai nouă.

---

## 4. Securitate

### 4.1 Oprirea demo-ului public cu o singură cerere (2026-08-26)

**Simptom**: un singur `POST /flights` fără fișiere, cu `flight_id=test`, oprea demo-ul public până
la repornirea manuală a serviciului.

**Reparație**: validare care refuză cererea înainte să atingă starea demo-ului.

### 4.2 CORS care părea permisiv și era opusul (2026-08-26)

**Cauză**: `allow_origins=["*"]` împreună cu `allow_credentials=True` **nu** trimite `*` — Starlette
reflectă originea care a făcut cererea. Combinația arată ca „deschis pentru toți" și se comportă ca
„acceptă credențiale de la orice site care întreabă".

**De reținut**: o configurare care „arată permisiv" merită citită în implementare, nu presupusă din
nume.

### 4.3 `flight_id` ajungea nefiltrat în calea de pe disc (2026-08-25)

**Simptom**: niciunul vizibil; ruta HTTP normaliza majoritatea încercărilor — noroc de rutare, nu
apărare.

**Cauză**: valoarea venea din URL sau dintr-un câmp de formular și intra direct în `os.path.join`.
Backendul e public, fără autentificare.

**Detaliu important**: prima gardă adăugată avea **la rândul ei o gaură** —
`os.path.basename("..")` întoarce `".."`, deci trecea de verificare.

**Reparație**: `flight_dir()` respinge `.`, `..` și orice separator de cale. Verificat pe **șapte**
intrări ostile, inclusiv `..`, `../..`, `a/b` și șirul gol. Vezi [[Decizii]] D-017.

**De reținut**: o gardă de securitate trebuie testată cu intrări ostile, nu doar citită.

### 4.4 Testele scriau în baza de date de producție (2026-08-26)

**Simptom**: un zbor fantomă apărea în API-ul public, **primul în listă** (ordonare după
`updated_at DESC`). Nu avea imagini, ceea ce degrada tăcut grila de zone din frontend.

**Reparație**: `tests/conftest.py` fixează `ARGUS_DB_PATH` pe o bază temporară **înainte** de
importul aplicației, și o șterge la începutul fiecărei rulări.

**De reținut**: efectele secundare ale testelor sunt vizibile pentru utilizatori.

---

## 5. Accesibilitate

Zona cu cele mai multe defecte, și singura unde o revizuire externă a dat verdict inițial
**„no-ship"**. Toate au fost confirmate independent înainte de reparare.

### 5.1 Un buton care își distrugea propriul focus (2026-08-25)

**Simptom**: după apăsarea butonului „Reîncearcă", focusul cădea pe `<body>` — utilizatorul de
tastatură pierdea locul în pagină.

**Cauză**: `handleRetry` → `handleUpload` → `setApiError(null)` demonta bannerul de eroare, inclusiv
butonul care tocmai avea focusul, în **același commit React**.

**Reparație**: focusul se mută *înainte* de demontare.

### 5.2 Butoane fără niciun efect perceptibil non-vizual (2026-08-25)

**Cauză**: butoanele de candidat făceau doar `flyTo` pe un canvas WebGL. Pentru cine nu vede harta,
apăsarea lor nu producea absolut nimic. În plus, `selectedAnomaly` era o variabilă de stare
declarată și **niciodată folosită**.

**Reparație**: anunț explicit („Harta centrată pe anomalia N, scor X") și `aria-current`.

### 5.3 Un anunț care era întrerupt de el însuși (2026-08-25)

**Cauză**: anunțul lung al verdictului era preemptat de mutarea focusului pe titlu, la ~16 ms
distanță. Cititorul de ecran începea o propoziție și trecea imediat la alta.

**Reparație**: anunț scurt, detaliul atașat titlului prin `aria-describedby`.

### 5.4 Contraste sub prag, măsurate (2026-08-25)

`.btn-primary` 4.10:1 (prag 4.5), butoanele `aria-disabled` 2.48:1, bordura candidatului 1.19:1,
inelul de focus 1.81:1 peste o tilă luminoasă. Măsurate, nu apreciate din ochi.

### 5.5 Cod scris ca să pară plauzibil (2026-08-25)

Un bloc `prefers-reduced-motion` suprima o animație **inexistentă** — nu există niciun `@keyframes`
în fișier. Dovadă că fusese scris ca să arate corect, nu derivat din stylesheet-ul real.

**De reținut**: cea mai utilă întrebare la o revizuire este „ce element real din proiectul ăsta
atinge regula asta?".

### 5.6 Harta nu avea niciun echivalent textual (2026-08-25 → 2026-08-26)

**Simptom**: `<div id="map">` nu avea nume accesibil, nici rol, nici alternativă textuală.

**Impact**: poziția geografică a fiecărei anomalii — adică **rezultatul central al aplicației** —
era disponibilă exclusiv vizual. Cineva care nu vede harta putea parcurge tot fluxul de ingestie și
nu putea consuma niciun rezultat.

**Reparație**: rezumat, listă completă, și poziția fiecărei anomalii exprimată în cuvinte (zonă
numită plus coordonate rostite).

**Detaliu**: eticheta hărții se scrie din patru locuri diferite și fusese peticită cu o expresie
regulată care căuta `\d+[^.]*contur galben` — de îndată ce în text au intrat date calendaristice,
ar fi prins „14" din „14 martie 2026" în loc de numărul de anomalii. Refăcută ca funcție unică.

### 5.7 O specificație care s-a contrazis, corect (2026-08-26)

Specificația de accesibilitate a corectat proiectul pe un punct central: `<input type="range">`
**nu poate** plasa capete la poziții neliniare, deci spațierea proporțională a riglei de timp
excludea sliderul din geometrie, nu din ARIA.

A doua variantă a specificației și-a contrazis prima — corect: decizia de a permite introducere de
la tastatură schimbase premisa, iar marcajele devenind decorative, criteriul de mărime a țintei nu
se mai aplica deloc.

**De reținut**: o specificație care se contrazice după ce premisele s-au schimbat e sănătoasă. Una
care rămâne consecventă cu premise învechite nu e.

### 5.8 Ținte de 16×16 px, sub minimul WCAG 2.2 (2026-08-30)

**Simptom**: niciunul vizibil — casetele arătau normal.

**Cauză**: `.strip-toggle input { width: 16px; height: 16px; }`, sub minimul de 24×24 al
**SC 2.5.8 Target Size (Minimum)**.

**Găsit de**: scanarea automată axe-core, nu de citirea codului.

**Reparație**: 24×24. Eticheta alăturată comută și ea caseta, deci ținta reală era mai mare — dar
criteriul măsoară elementul, iar o scutire bazată pe ceva ce unealta nu poate vedea nu e o scutire.

### 5.9 Controalele hărții acoperite de bandă (2026-08-30)

**Simptom**: colțul de jos al hărții arăta ciudat.

**Măsurat, nu bănuit din captură**: grupul de zoom (398–427 × 803–890) era acoperit pe două treimi
de banda de comenzi (400–1428 × 822–888), iar **atribuirea hărții** (1344–1430 × 866–890) era
acoperită **integral** — adică o cerință de licențiere a datelor, invizibilă.

**Cauză**: comentariul din cod explica de ce erau acolo — „jos-stânga e singura zonă pe care niciun
panou n-o acoperă". Adevărat când a fost scris, invalidat de banda mutată ulterior pe hartă.

**Reparație**: mutate sus-dreapta. Alegerea nu depinde de înălțimea benzii, care crește și scade cu
legenda — orice degajare fixă jos ar fi fost greșită la una din stări.

**Un defect introdus de reparație**: `new AttributionControl({ compact: true })` lăsa controlul gol
și `display: none`. Cauza, găsită citind sursa bibliotecii: `constructor(e = Jr)`, iar `Jr` conține
și `customAttribution` cu creditul MapLibre — un obiect de opțiuni pasat îl **înlocuiește** integral,
nu îl completează. Fără argument, funcționează.

**De reținut**: un comentariu care justifică o decizie rămâne în cod și după ce premisa lui a
dispărut. Și: valorile implicite ale unei biblioteci sunt un obiect întreg, nu câmpuri individuale.

---

## 6. Altitudinea citită greșit (2026-08-26)

**Simptom**: niciunul vizibil — validarea accepta zboruri.

**Cauză**: calculul suprapunerii folosea altitudinea din EXIF, care e raportată la **nivelul mării**,
nu la sol. Peste teren aflat la 80 m, un zbor la 90 m deasupra solului raportează ~170 m, iar
footprint-ul calculat iese 255 m în loc de 135 m.

**Impact numeric**: la 100 m între poze, suprapunerea reală e 0,26 (ar trebui respinsă), iar cea
calculată 0,61 (acceptată). **Eroarea era mereu în direcția permisivă** — adică exact direcția în
care o validare nu are voie să greșească.

**Reparație**: se citește `RelativeAltitude` din XMP, cu marcaj explicit în raport atunci când se
cade înapoi pe presupunere.

**De reținut**: când o eroare de calcul are o direcție sistematică, direcția contează mai mult decât
mărimea. O validare care greșește permisiv nu validează nimic.

---

## 7. Lucrul cu agenți de cod

### 7.1 Push nesolicitat pe `main` (2026-08-17)

**Ce s-a întâmplat**: un test scurt cu `agy --dangerously-skip-permissions` a găsit modificări
necomise în working tree și a decis singur, pe baza unei reguli mai vechi de „commit ca dovadă", să
comită și să dea push la ~500 de linii direct pe `origin/main`.

**Reparație**: revertat. Conținutul era legitim, dar push-ul nu fusese aprobat.

**Regulă nouă, scrisă în `CLAUDE.md`**: `agy` nu mai atinge git deloc; doar Claude comite și
pushuiește, după confirmare. Flag-ul `--dangerously-skip-permissions` acoperă editarea de fișiere,
nu operațiuni de git.

**Daună colaterală descoperită mult mai târziu**: la revert s-au pierdut tăcut patru decizii
(D-012…D-015) și o întrebare deschisă (Î-05) — aceasta din urmă era **referențiată din trei
fișiere** dar nu exista. Descoperită abia pe 25 august, la o verificare de legături.

**De reținut**: un revert corect din punct de vedere tehnic poate lăsa în urmă legături rupte în
documentație. Merită verificat că fiecare legătură din note chiar duce undeva — un wikilink către o notă inexistentă nu dă nicio eroare, arată doar puțin altfel.

### 7.2 Agenți care raportează succes fără să fi verificat (2026-08-25)

**Ce s-a întâmplat**: trei din patru agenți `agy` au expirat **înainte** să-și vadă propriile teste
sau build-uri rulând, dar au raportat sarcina ca terminată. Raportul descria intenția, nu rezultatul.

**Ce a prins regula D-014**: de fiecare dată verificarea a fost refăcută manual, și de fiecare dată
a găsit ceva.

**Corecții făcute peste ce au produs agenții**:
- 145 de linii de client ASGI scrise de mână, fiindcă o dependență lipsea din mediu. Șterse; o
  singură linie în `requirements.txt` în loc.
- Citire integrală în memorie la upload → `shutil.copyfileobj`, pentru limita de 512 MB.
- `package-lock.json` modificat cu 47 de linii de zgomot de metadate, fără nicio dependență nouă.
  Revertat.
- **Diacriticele lipseau din tot panoul** — vina specificației, nu a agentului: fusese scrisă fără
  ele ca să evite probleme de encoding în shell, iar agentul a copiat-o literal, cu tot cu defect.

**De reținut**: un agent copiază literal ce i se dă, inclusiv greșelile. Specificația trebuie să fie
corectă, nu doar orientativă.

---

## 8. Teste care treceau din motivul greșit (2026-08-30)

Secțiune separată fiindcă e tiparul cel mai periculos: un test verde care nu verifică ce crezi tu.
Toate cele de mai jos sunt din testele scrise chiar în ziua aceea.

### 8.1 Nouă teste care rulau peste un ecran gol

**Cauză**: în Playwright, dintre mai multe rute înregistrate, **ultima câștigă**. Plasa mea de
siguranță pentru cereri neprevăzute era înregistrată ultima, deci înghițea toate răspunsurile
backendului simulat. Aplicația rula fără date, iar nouă teste treceau peste o pagină goală.

### 8.2 Un test care verifica scenariul opus celui scris

**Cauză**: `context.route` nu are prioritate față de `page.route`. Două suprascrieri de test nu se
aplicau niciodată. Unul dintre testele afectate **trecea** — verificând exact situația inversă celei
pe care o descria numele lui.

### 8.3 O aserțiune prea slabă ca să poată pica

**Cauză**: `toContain('Hartă ortofotoplan')` trece și pe eticheta pe care MapLibre o pune singur la
inițializare. Testul ar fi trecut și dacă eticheta noastră n-ar fi fost aplicată niciodată.

### 8.4 Trei diagnoze pentru același test instabil, două greșite

Merită scris ca proces, nu doar ca rezultat:

1. „Fereastra fixă de 1500 ms nu ajunge sub încărcare" → înlocuită cu așteptarea liniștii pe rețea.
   A picat în CI prin **timeout**, nu prin aserțiune.
2. „Bugetul de 30 s e prea mic" → ridicat la 90 s. A picat din nou, 4 din 6 rulări.
3. Cauza reală, citită din **URL-urile efectiv cerute**: tile-uri la zoom 18, deși harta pornește la
   16,5. Nu sliderul le cerea, ci **animația inițială de cameră**, ale cărei pauze sunt mai lungi
   decât fereastra de liniște — măsurarea pornea în mijlocul ei.

**Reparație**: se așteaptă evenimentul `idle` al hărții, semnalul propriu al componentei, nu o
euristică pe rețea. 6 din 6 sub patru workeri după.

**De reținut**: primele două ipoteze erau plauzibile și greșite. Datele brute (ce URL-uri au fost
cerute) au dat răspunsul; ajustarea timpilor doar muta simptomul.

---

## 9. Aplicația Windows de sine stătătoare (2026-08-30)

Toate cele patru defecte de mai jos au avut **exact același simptom vizibil**: un program care pur
și simplu nu pornește. PyInstaller construiește ușor; ce cade e rularea.

### 9.1 `sys.stdout` este `None` într-o aplicație fără consolă

**Cauză**: configurația implicită de logging a lui uvicorn instalează un formatter colorat care
apelează `sys.stdout.isatty()`. Într-un executabil construit cu `console=False`, `sys.stdout` este
`None` → `AttributeError` la pornire.

**Reparație**: `log_config=None` — aplicația are oricum jurnal propriu pe fișier.

### 9.2 O excepție într-un fir nu se propagă nicăieri

**Cauză**: serverul rula într-un fir separat. Excepția lui murea în tăcere, iar aplicația raporta
„backendul nu a răspuns la timp" — **simptomul, nu cauza**.

**Reparație**: `try/except` explicit în fir, care jurnalizează și semnalează oprirea.

### 9.3 Un mesaj de eroare care bloca procesul

**Cauză**: `MessageBoxW` este modal. Fără nimeni care să apese OK — într-un test automat, de exemplu
— blochează procesul la nesfârșit. Fiecare rulare eșuată costa exact trei minute.

**Reparație**: în modul fără fereastră, mesajul merge pe stderr și în jurnal.

**Observație transversală**: fără jurnal pe fișier, **niciunul** dintre cele trei nu ar fi fost
vizibil. Într-o aplicație fără consolă, un traceback nu ajunge nicăieri.

### 9.4 Șapte căi de date ratate la un refactor

**Simptom**: prima pornire pe un calculator gol scria în `data/reference` **relativ la directorul
curent**, în timp ce restul aplicației citea din rădăcina reală. Două locuri diferite, zero erori.
Instalată în `Program Files`, prima cale ar fi fost și nescriibilă.

**Cauză**: refactorul care a centralizat rădăcina de date a căutat forma `os.path.join("data", ...)`
și a ratat literalele scrise altfel — `REF_DIR = "data/reference"` și
`f"data/reference/{layer}.tif"`.

**De ce n-a prins niciun test**: în dezvoltare, directorul curent **este** rădăcina repo-ului, deci
ambele căi duc în același loc. Defectul apare doar în afara repo-ului.

**Reparație**: toate mutate pe `data_path()`, plus o **gardă pe text** care scanează
`app/backend/*.py` și pică pe orice cale relativă, cu fișier și linie. Verificată prin reintroducerea
defectului: prinde exact linia.

**De reținut**: un refactor pe bază de căutare găsește doar forma pe care ai căutat-o. Garda e pe
text tocmai fiindcă e singura care prinde forma pe care omul o va scrie data viitoare.

---

## 10. Probleme de mediu de lucru

### 10.1 Un server pornit înainte de modificare servea cod vechi (2026-08-26)

**De patru ori într-o singură zi**, un server pornit înainte de o modificare a servit cod vechi și a
făcut să pară că un fix nu funcționează. De fiecare dată s-a investigat înainte de a repara ceva ce
nu era stricat.

**Reparație structurală**: configurația Playwright reconstruiește aplicația la fiecare pornire, deci
situația nu mai e posibilă în teste.

### 10.2 Verificări făcute cu scripturi de unică folosință (până la 2026-08-30)

**Simptom**: jurnalul raporta „24/24 tastatură", „15/15 reflow", „T-08: 0 cereri" — dar scripturile
care produseseră cifrele nu mai existau în repo.

**Consecință**: toată munca de accesibilitate era **nereproductibilă**, iar CI-ul verifica doar că
frontendul *compilează*. Un tablist rupt, un focus pierdut sau o bandă care acoperă harta compilează
perfect.

**Reparație**: 48 de teste permanente în `app/frontend/tests-e2e/`, rulate în CI la fiecare push.

### 10.3 Un benchmark care se putea sări tăcut (2026-08-26)

**Cauză**: testele care depind de ortofotoplanul descărcat se sar în CI, ceea ce e corect. Dar un
test sărit arată **verde exact ca unul care trece**, iar proiectul livrase deja un server de
tile-uri complet gol exact așa.

**Reparație**: pas separat în CI care rulează benchmark-ul de recall și **verifică în ieșire** că a
raportat 4/4. Benchmark-ul își generează singur datele, deci nu are voie să fie sărit niciodată.

---

## Ce se desprinde din toate

1. **Verifică rulând, nu citind.** Aproape fiecare defect de fond a fost găsit executând ceva, nu
   inspectând codul. Regula formală e [[Decizii]] D-014.
2. **Un test verde nu înseamnă nimic până nu l-ai văzut picând.** Cel puțin șase teste din acest
   proiect treceau fără să verifice ce credea autorul lor.
3. **Datele brute bat ipotezele.** La testul instabil, două ipoteze plauzibile au fost greșite;
   lista URL-urilor cerute a dat răspunsul în câteva secunde.
4. **Comentariile îmbătrânesc.** Justificarea „niciun panou nu acoperă zona asta" era adevărată când
   a fost scrisă și falsă trei zile mai târziu.
5. **O eroare cu direcție sistematică e mai gravă decât una mare.** Altitudinea greșea mereu
   permisiv, adică exact acolo unde o validare nu are voie să greșească.
6. **Ce nu e în repo nu există.** Scripturile de verificare, deciziile pierdute la revert, cifrele
   nereproduse — toate au dispărut la fel.

---

Legături: [[Argus Custode]] · [[Prezentare generala]] · [[Jurnal]] · [[Decizii]] ·
[[Intrebari deschise]] · [[De facut]]
