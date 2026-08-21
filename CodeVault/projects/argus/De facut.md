---
tags: [argus, todo]
created: 2026-08-17
type: todo
---

# De făcut

Proiect: [[Argus Custode]]. Tot ce a rămas deschis la finalul sesiunii de azi (2026-08-17), ca să nu se piardă până la reluare — pe orice mașină. Ordonate aproximativ după cât de mult contează.

## 1. ~~Faza 7 — deployment real~~ — LIVE, verificat independent (2026-08-21)

Ambele componente sunt public accesibile, fără login, verificate cu `curl`/`vercel curl` din afara conversației (nu doar status API):

- **Backend**: `https://argus-backend-yw3h.onrender.com` (Render, free tier). Trei eșecuri reale rezolvate pe drum — vezi [[Jurnal]] 2026-08-21: Python 3.11→3.12 în `Dockerfile` (numpy n-avea wheel), apoi două runde de OOM (exit 137) reparate prin streaming pe ferestre (`rasterio.windows.Window`) în `provision.py`/`detect.py` și downsampling la 3000px pe latura lungă.
- **Frontend**: `https://argus-agheoronos-projects.vercel.app` (Vercel). SSO protection era activă implicit pe tot proiectul (inclusiv producție) — dezactivată explicit cu acordul utilizatorului, altfel linkul nu era deschis public.

De reținut pentru viitor: `VITE_API_BASE` trebuie adăugat separat pe Production **și** Preview în Vercel — CLI-ul nu propagă automat între medii.

## 2. Recall T-05 — rezolvat parțial (2026-08-19), zona vegetație rămâne nedetectată

Cifrele de 4/4 din [[Jurnal]] (2026-08-17) nu s-au reprodus la verificare independentă pe mașina desktop — vezi corecția din [[Jurnal]] (2026-08-19) și [[Decizii]] D-009. `top_n` implicit a fost crescut la 50 (îmbunătățire reală, măsurată: 2/4 → 3/4), dar zona „Vegetation clearing" nu apare în top-100+ pe nicio configurație testată. De decis, dacă rămâne timp: feature dedicat pentru schimbări de vegetație/contrast (ex. raport de canale similar NDVI), în loc de doar tunat `top_n`/`patch`.

## 3. T-08 — sliderul, testat doar prin code review

Am confirmat prin citirea codului că `setPaintProperty` nu poate face cereri de rețea prin design (MapLibre GL), dar **nu am rulat testul manual cerut de task** (DevTools → Network, mișcat sliderul, verificat 0 cereri noi) — n-am avut browser la dispoziție. Merită 2 minute de test real înainte să declari T-08 complet verificat.

## 4. Decizii pierdute la revert, nerescrise

D-008…D-011 originale (COG vs. pre-tiling, evaluare pe adevăr sintetic, verificare mecanică, licența AGPL a ODM) au fost șterse la revert-ul commit-ului `d24a97f` și nu au fost rescrise — deși tot ce descriau chiar s-a implementat între timp (COG la T-06, perechea sintetică la T-03). `D-008` există acum din nou în [[Decizii]], dar cu alt conținut (seed pe disc efemer Render). Pur documentație lipsă, nu blochează codul.

## 5. Curățenie cosmetică, minoră

`CodeVault/AGENTS.md` și `CodeVault/CLAUDE.md` au pierdut BOM-ul UTF-8 la o resalvare; `Index.md`, `Decizii.md`, `Intrebari deschise.md` au terminatori de linie inconsistenți (CRLF/LF) — apar „modificate" în git fără conținut real schimbat. Cerut o dată să se rezolve, nu s-a făcut niciodată. Zero impact funcțional.

## 6. ~~Verifică plugin-ul Obsidian Git~~ — confirmat instalat (2026-08-19)

Confirmat de utilizator: Obsidian Git e instalat și funcțional pe mașina principală.

## 7. Stretch, neînceput

- **Faza 1** — ingestie și validare pe date reale de zbor (blur, overlap, GPS EXIF).
- **Faza 2** — fotogrammetrie cu OpenDroneMap (Docker, ore de procesare, licență AGPL de clarificat — vezi [[Intrebari deschise]] Î-05).

---

Reluare rapidă pe altă mașină: `git pull`, `setup-skills.ps1`/`.sh` dacă e prima dată, citește [[Jurnal]] de sus în jos pentru context, apoi ia lista de mai sus de la 1.
