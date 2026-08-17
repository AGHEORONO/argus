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

## D-008 — COG în loc de pre-tiling (2026-08-17)

Rasterele se stochează ca Cloud Optimized GeoTIFF și se servesc prin range request, nu se taie în tile-uri pre-generate.
**De ce**: elimină un pas de procesare de minute după fiecare zbor și mii de fișiere de gestionat. Decizie luată acum pentru că e ieftină la început și scumpă după ce construiești peste ea. Detalii în [[Performanta]].

## D-009 — Evaluare pe adevăr sintetic, de la început (2026-08-17)

Perechea before/after cu schimbări injectate (T-03) se construiește **înainte** de algoritmul de detecție.
**De ce**: fără adevăr cunoscut, „funcționează" e o părere. Cu el, ai o cifră. Cifra e și ce vinde proiectul la concurs — vezi [[Caiet de practica]] — și singura protecție reală când execuția e delegată unui model ieftin.

## D-010 — Verificare mecanică, nu de încredere (2026-08-17)

Un singur `check.py` la rădăcină, rulat după fiecare task; niciun task nu se închide fără output lipit în [[Jurnal]].
**De ce**: execuția e delegată către modele rapide și ieftine (Sonnet, Gemini Flash), cu verificare finală de către Opus. Fiabilitatea nu vine din instrucțiuni mai bune, ci din checkuri care pică zgomotos. Vezi [[Reguli pentru agent executant]].

## D-011 — Perspectiva comercială schimbă tratamentul licențelor (2026-08-17)

Orice dependință se alege ținând cont că produsul ar putea fi vândut. Licențele copyleft se semnalează, nu se ignoră.
**Consecință imediată**: ODM e AGPL-3.0, deci faza 2 devine și un risc juridic, nu doar unul de hardware. Deschis ca Î-05 în [[Intrebari deschise]]. Nu blochează nimic acum — faza 2 e oricum ultima.
