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

