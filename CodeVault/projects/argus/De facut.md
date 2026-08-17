---
tags: [argus, todo]
created: 2026-08-17
type: todo
---

# De făcut

Proiect: [[Argus Custode]]. Tot ce a rămas deschis la finalul sesiunii de azi (2026-08-17), ca să nu se piardă până la reluare — pe orice mașină. Ordonate aproximativ după cât de mult contează.

## 1. Faza 7 — deployment real (config gata, nimic live încă)

`Dockerfile`, `render.yaml`, `vercel.json`, `app/backend/provision.py`, `app/frontend/.env.example` există și par corecte (verificate prin citirea codului), dar **niciun deployment real nu s-a întâmplat** — un URL raportat anterior (`argus-backend.onrender.com`) era fabricat, nu exista. Vezi [[Jurnal]], corecția din 2026-08-17.

De făcut, manual, cu cont propriu:
- Cont Render → Web Service nou din `AGHEORONO/argus`, folosind `Dockerfile`/`render.yaml`.
- Cont Vercel → import `AGHEORONO/argus`, root `app/frontend`, `VITE_API_BASE` = URL-ul real de pe Render.
- **Dockerfile-ul nu a fost testat nici măcar local** (nu există Docker instalat pe mașina asta) — posibil să nu se builduiască din prima încercare (GDAL + rasterio au uneori conflicte de versiune între `apt` și `pip`).

## 2. Recall T-05 — 3/4, nu 4/4, la parametrii impliciți

`detect_changes()` are implicit `patch=32, top_n=20` → recall 3/4 (75%), verificat independent. Din experimentele din [[Jurnal]] (2026-08-17, T-05): `top_n=50` sau `patch=16` ajung la 4/4 (100%), dar **niciuna din variante nu a fost setată ca implicit** în cod sau în backend. De decis: schimbi implicitul, sau rămâne 3/4 cu argumentare explicită în [[Decizii]].

## 3. T-08 — sliderul, testat doar prin code review

Am confirmat prin citirea codului că `setPaintProperty` nu poate face cereri de rețea prin design (MapLibre GL), dar **nu am rulat testul manual cerut de task** (DevTools → Network, mișcat sliderul, verificat 0 cereri noi) — n-am avut browser la dispoziție. Merită 2 minute de test real înainte să declari T-08 complet verificat.

## 4. Decizii pierdute la revert, nerescrise

D-008…D-011 originale (COG vs. pre-tiling, evaluare pe adevăr sintetic, verificare mecanică, licența AGPL a ODM) au fost șterse la revert-ul commit-ului `d24a97f` și nu au fost rescrise — deși tot ce descriau chiar s-a implementat între timp (COG la T-06, perechea sintetică la T-03). `D-008` există acum din nou în [[Decizii]], dar cu alt conținut (seed pe disc efemer Render). Pur documentație lipsă, nu blochează codul.

## 5. Curățenie cosmetică, minoră

`CodeVault/AGENTS.md` și `CodeVault/CLAUDE.md` au pierdut BOM-ul UTF-8 la o resalvare; `Index.md`, `Decizii.md`, `Intrebari deschise.md` au terminatori de linie inconsistenți (CRLF/LF) — apar „modificate" în git fără conținut real schimbat. Cerut o dată să se rezolve, nu s-a făcut niciodată. Zero impact funcțional.

## 6. Verifică plugin-ul Obsidian Git

[[Decizii]] D-005 zice că sincronizarea notelor se face prin plugin-ul Obsidian Git (auto-commit + auto-pull), separat de git CLI pentru cod — dar nu am verificat dacă e chiar instalat și configurat pe această mașină (`.obsidian/community-plugins.json`). De confirmat înainte să te bazezi pe el pe laptop.

## 7. Stretch, neînceput

- **Faza 1** — ingestie și validare pe date reale de zbor (blur, overlap, GPS EXIF).
- **Faza 2** — fotogrammetrie cu OpenDroneMap (Docker, ore de procesare, licență AGPL de clarificat — vezi [[Intrebari deschise]] Î-05).

---

Reluare rapidă pe altă mașină: `git pull`, `setup-skills.ps1`/`.sh` dacă e prima dată, citește [[Jurnal]] de sus în jos pentru context, apoi ia lista de mai sus de la 1.
