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
