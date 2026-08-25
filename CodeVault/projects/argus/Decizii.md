---
tags: [argus, decizii]
created: 2026-08-17
type: decizii
---

# Decizii

Proiect: [[Argus Custode]]. Fiecare decizie cu motivul ei, ca să nu se redeschidă discuția peste trei săptămâni. Dacă o decizie se schimbă, nu o ștergi — adaugi una nouă care o înlocuiește.

## D-001 — Numele: Argus Custode (2026-08-17)

Scurt `argus` în repo, cod și comenzi. Full **Argus Custode** pentru prezentare.
**De ce**: Argus e paznicul cu o sută de ochi care nu doarme — exact funcția aplicației. *Custode* e identic în română și italiană, cu același sens, deci numele nu are nevoie de traducere. Ține linia mitologică deja începută cu Nereus.

## D-002 — Un singur repo, privat (2026-08-17)

Repo `AGHEORONO/argus`, privat, conținând și notele, și codul.
**De ce**: un singur `git clone` pe laptop, o singură sincronizare de întreținut. Privat pentru că practica poate implica cerințe sau date ale firmei.
**Consecință**: granița cod ↔ note e ținută curată de la început (`CodeVault/` separat de codul aplicației), ca la final să poți fie comuta tot repo-ul pe public, fie extrage doar codul într-un repo public. Vizibilitatea se schimbă oricând din Settings, fără pierdere de istoric.

## D-003 — Stack reutilizat de la Nereus (2026-08-17)

FastAPI + SQLite, React/Vite + MapLibre, Isolation Forest.
**De ce**: singurele bucăți cu risc tehnic nou rămân fotogrammetria și tiling-ul. Restul e teren cunoscut, deci timpul se duce în ce e nou, nu în relearning.

## D-004 — Ordinea de execuție inversată față de pipeline (2026-08-17)

Se începe cu faza 4 (detecția), nu cu faza 1 (ingestia). Fotogrammetria e ultima.
**De ce**: fazele 1-2 depind de date de zbor și de hardware, ambele necunoscute acum. Faza 4 nu depinde de nimic din afară și e partea cea mai vizibilă. Detalii în [[Plan de implementare]].

## D-005 — Sync dublu: Obsidian Git + CLI (2026-08-17)

Plugin Obsidian Git pentru note (auto-commit + auto-pull), git din CLI pentru cod.
**De ce**: notele se scriu în rafale scurte și dese, unde commit-ul manual devine fricțiune; codul are nevoie de commit-uri deliberate, cu mesaj.
**Consecință**: `.obsidian/workspace.json` e în `.gitignore` — altfel cele două mașini se calcă reciproc pe starea de UI la fiecare pull.

## D-006 — Note în română, cod în engleză (2026-08-17)

**De ce**: practica se gândește și se prezintă în română; codul, commit-urile și numele de fișiere în engleză rămân standard și nu te blochează dacă repo-ul devine public.

## D-007 — Fără Celery, Redis sau PostGIS la start (2026-08-17)

`BackgroundTasks` din FastAPI și SQLite.
**De ce**: la volumul unui proiect de practică sunt servicii în plus de întreținut pentru zero câștig. Se adaugă doar când apare o nevoie măsurată — joburi paralele reale sau query-uri spațiale pe care SQLite nu le poate face.

## D-008 — Seed automat demo pe disc efemer (Render) (2026-08-17)

La pornirea backend-ului în `lifespan`, se verifică și se seedează automat datele de referință (`before.cog.tif`, `after.cog.tif`) și zborul `test` cu detecția pre-calculată.
**De ce**: Render (tier gratuit) șterge discul efemer la fiecare restart/redeploy după inactivitate. Pentru demo public, utilizatorul trebuie să poată deschide linkul și să vadă imediat harta și anomaliile fără să fie nevoie de re-upload manual.
**Consecință / Notă de producție**: la trecerea la date reale de producție este obligatoriu storage persistent extern (AWS S3 / Cloudflare R2 pentru rastere și PostgreSQL / PostGIS gestionat pentru metadata).

## D-009 — `top_n` implicit crescut la 50, fără a pretinde 4/4 (2026-08-19)

Implicit `top_n=20` → `50` în `detect_changes()`, `run_detection_job()`, seed-ul din `provision.py`.
**De ce**: măsurat independent pe mașina desktop, recall crește de la 2/4 la 3/4 (vezi [[Jurnal]] 2026-08-19), fără cost suplimentar de calcul (`patch` neschimbat). Cifrele de 4/4 raportate anterior în [[Jurnal]] (2026-08-17, T-05) nu s-au reprodus și sunt tratate ca nesigure.
**Rămâne deschis**: zona „Vegetation clearing" nu apare în top-100+ candidați pe nicio configurație testată — nu e o problemă de prag/`top_n`, pare o limitare reală a feature-urilor curente pentru schimbări de tip vegetație/contrast. Nu s-a rezolvat, doar documentat.

## D-010 — Raster demo redus la max 3000px pe latura lungă, pentru Render free tier (2026-08-21)

`downsample_if_needed()` reduce `before.tif` la provisioning, cu citire decimată GDAL (nu materializează rezoluția completă în memorie). Zonele sintetice din `generate_synthetic_pair()` sunt scalate proporțional față de rezoluția originală (8959×13066), nu mai sunt constante fixe.
**De ce**: chiar și cu citire pe ferestre (streaming, fără fix separat de decizie), `build_cog()` + antrenarea Isolation Forest tot depășeau 512MB pe rasterul aproape la rezoluție completă — OOM (exit 137) confirmat de două ori în log-urile Render. Rezoluția redusă a fost singura variantă care a dus efectiv la un deploy `live`, verificat.
**Consecință**: demo-ul public rulează la rezoluție mai mică decât ce ai local. Recall-ul măsurat la această rezoluție a ieșit 4/4 (mai bun decât 3/4 la full res) — notat cinstit, nu explicat pe deplin.

## D-011 — SSO protection dezactivată pe proiectul Vercel (2026-08-21)

`vercel project protection disable argus --sso`, confirmat explicit de utilizator înainte de execuție.
**De ce**: implicit, Vercel pune SSO protection pe toate deploy-urile unui proiect de tip echipă (`ssoProtection.deploymentType: all_except_custom_domains`) — inclusiv producție. Contrazicea direct obiectivul Fazei 7 („cineva deschide un link, vede demo-ul, fără login"). Verificat înainte și după cu `curl`: înainte, 302 către `vercel.com/sso-api`; după, 200 direct.
**Consecință**: oricine cu link-ul vede demo-ul, inclusiv API-ul de backend din spate (deja fără protecție, CORS deschis `allow_origins=["*"]`). Acceptabil pentru un proiect de practică cu date sintetice publice; de reconsiderat dacă la un moment dat conține date reale sensibile ale firmei.

## D-012 — COG cu tiling dinamic, nu pre-tiling în piramidă de fișiere PNG (2026-08-17)

Rasterele sunt stocate ca Cloud Optimized GeoTIFF (`build_cog` cu `rio-cogeo`, profil `deflate`) și tile-urile XYZ sunt generate la cerere de backend din COG (`app/backend/tiles.py`, cu cache de dataset și Pillow), în loc să fie pre-generat un arbore de tile-uri PNG pe disc. *(Rescrisă după pierderea la revert-ul commit-ului `d24a97f`.)*
**De ce**: pre-tiling-ul înseamnă mii de fișiere mici, timp de generare la fiecare raster nou și spațiu pe disc multiplicat; COG-ul are deja overview-uri interne și permite citire pe intervale, deci un singur fișier acoperă toate nivelurile de zoom. În plus, pe disc efemer (Render free tier) un singur fișier se re-generează mult mai simplu decât un arbore de directoare.
**Consecință**: costul se mută de la stocare la CPU per cerere de tile, atenuat de cache-ul de dataset.

## D-013 — Evaluare pe adevăr sintetic, nu pe apreciere vizuală (2026-08-17)

Perechea before/after este generată programatic (`generate_synthetic_pair` în `app/backend/provision.py`), cu zone de schimbare injectate la coordonate cunoscute, și adevărul de referință scris în `data/reference/truth.geojson`. Calitatea detecției se măsoară ca recall pe aceste zone cunoscute. *(Rescrisă după pierderea la revert-ul commit-ului `d24a97f`.)*
**De ce**: fără adevăr cunoscut, „merge bine" e o părere. Cu perechea sintetică există o cifră reproductibilă (câte zone din adevăr apar în top-N candidați), care poate fi comparată între configurații și între mașini.
**Consecință**: cifra măsoară doar tipurile de schimbare injectate, nu performanța pe date reale de zbor; e o limită inferioară utilă, nu o validare finală.

## D-014 — Verificare mecanică înainte de a declara un task terminat (2026-08-17)

Nicio fază sau task nu este declarat gata pe baza citirii codului sau a unui status API; trebuie o dovadă rulată (comandă, output, cifră) notată în [[Jurnal]]. *(Rescrisă după pierderea la revert-ul commit-ului `d24a97f`.)*
**De ce**: pe 2026-08-17 un rezultat de recall a fost raportat fără să fi fost reprodus și ulterior nu s-a mai confirmat la re-verificare. Costul unei verificări e de ordinul minutelor; costul unei afirmații false care se propagă în decizii ulterioare e mult mai mare.
**Consecință**: fiecare intrare din [[Jurnal]] are o secțiune de output verificat.

## D-015 — Licența AGPL a OpenDroneMap, clarificată înainte de Faza 2 (2026-08-17)

ODM se folosește ca proces separat, rulat în Docker, care produce un ortofotoplan consumat de backend ca fișier; nu se leagă cod ODM în aplicație. Întrebarea de licență rămâne deschisă formal în [[Intrebari deschise]] Î-05 și trebuie clarificată înainte ca Faza 2 să fie livrată către firmă. *(Rescrisă după pierderea la revert-ul commit-ului `d24a97f`.)*
**De ce**: ODM e AGPL; un serviciu accesibil prin rețea care încorporează cod AGPL poate atrage obligația de a pune la dispoziție sursa. Rularea ca binar separat, cu schimb de fișiere, este modelul care ridică cele mai puține întrebări, dar nu înlocuiește o clarificare explicită.
**Rămâne deschis**: statutul exact pentru un eventual deployment comercial al firmei.

## D-016 — Suprapunerea se estimează din GPS și footprint, nu din potrivire de trăsături (2026-08-25)

`estimate_overlap()` calculează fracția de suprapunere dintre două poze consecutive din distanța haversine între pozițiile GPS și lățimea de teren acoperită (`ground_footprint_m()` = altitudine × lățime senzor / focală). Nu se face potrivire de trăsături între imagini.
**De ce**: potrivirea de trăsături costă secunde per pereche și ar transforma validarea „de 5 secunde la intrare" exact în lucrul pe care validarea trebuie să-l evite. EXIF-ul de dronă are deja tot ce trebuie: GPS, altitudine, focală, echivalent 35mm. Verificat pe optica unui DJI Phantom 4 (focală 8.8 mm, echivalent 24 mm → senzor 13.2 mm): la 90 m altitudine iese footprint de 135.0 m, iar la 12 m între poze, suprapunere 0.911.
**Consecință**: e o aproximare pe o singură axă, folosind lățimea footprint-ului indiferent de direcția de zbor, și cade complet fără GPS (întoarce `None`, poza primește `no_gps`, nu o cifră inventată). Suficient ca să prinzi un zbor cu spacing greșit; insuficient ca să validezi geometria fină a unui bloc fotogrammetric.
**Rămâne deschis**: nu a fost testată niciodată pe o poză reală de dronă — doar pe fixture-uri sintetice cu EXIF scris de noi. Prima dată când apar date reale de zbor, primul lucru de verificat e că tag-urile EXIF chiar se citesc așa cum presupune codul.

## D-017 — `flight_id` sanitizat înainte de a atinge sistemul de fișiere (2026-08-25)

`flight_dir()` respinge `.`, `..` și orice `flight_id` care conține un separator de cale, înainte ca valoarea să ajungă în `os.path.join`. Aplicat pe toate endpoint-urile care construiesc căi din `flight_id`, nu doar pe cele noi.
**De ce**: `flight_id` vine din URL sau dintr-un câmp de formular și era băgat direct în calea de pe disc. Backend-ul e public, fără autentificare și cu CORS deschis (vezi [[Decizii]] D-011) — deci oricine putea încerca să scrie în afara directorului `data/flights`. Ruta HTTP normaliza deja majoritatea încercărilor, dar asta e noroc de rutare, nu apărare.
**Consecință**: ID-urile de zbor sunt limitate la nume simple de director. Verificat pe șapte intrări ostile, inclusiv `..`, `../..`, `a/b`, `a` și șirul gol.

## D-018 — Un sit are N capturi datate; comparația e între oricare două (2026-08-25)

Model nou, adăugat pe lângă cel existent, nu în locul lui: **sit** (loc monitorizat) → **capturi** (o imagine, o dată) → **comparații** (detecție între oricare două capturi ale aceluiași sit). `app/backend/sites.py`, tabele separate, endpoint-urile `/flights` rămân neatinse și continuă să servească demo-ul.
**De ce**: modelul vechi făcea ca un „zbor" să însemne o **pereche** de rastere, deci comparația era fixată la încărcare și nu putea fi decât între exact doi termeni. O firmă de topografie zboară același sit lunar și vrea progresia, nu un singur salt. Perechea e unitatea greșită. În plus, modelul nou face ca fluxul de ingestie de fotografii să se potrivească natural: un set de poze produce **o captură**, nu o pereche.
**Consecință**: baza de referință e mereu captura mai veche, indiferent de ordinea argumentelor — altfel aceeași pereche s-ar putea stoca de două ori cu sensuri opuse, iar „ce s-a schimbat din martie" ar depinde de ce câmp a completat utilizatorul primul. Index unic pe perechea ordonată, deci o re-rulare actualizează rândul existent în loc să adauge unul care contrazice.
**Detaliu care contează**: datele se stochează ca text ISO-8601, fiindcă SQLite n-are tip de dată iar ISO se sortează corect ca șir. O dată în format liber ar rupe tăcut ordinea cronologică pe care se sprijină tot timeline-ul, deci intrarea e validată la primire.
**Rămâne deschis**: interfața încă folosește modelul vechi. Rigla de timp vine ca etapă separată, ca să nu se construiască UI peste un model care se mai poate mișca.
