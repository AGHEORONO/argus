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

## 2. ~~Recall T-05~~ — 4/4, confirmat pe datele curente de producție (2026-08-21)

Traseu complet: 3/4 (17 aug, neverificat/nereprodus) → 2/4 (19 aug, verificare independentă pe desktop, `top_n=20`) → 3/4 (`top_n=50`, tot fără zona de vegetație) → **4/4** (21 aug, după downsampling-ul din D-010 — zona de vegetație a devenit detectabilă la rezoluția redusă, efect secundar neplanificat). Verificat riguros cu `detect_changes()` la parametrii impliciți din cod, pe fișierele exact ca în producție. Nu s-a mai investigat *de ce* rezoluția mai mică ajută (posibil netezire/reducere zgomot din resampling) — funcțional, e rezolvat.

## 3. T-08 — sliderul, testat doar prin code review

Am confirmat prin citirea codului că `setPaintProperty` nu poate face cereri de rețea prin design (MapLibre GL), dar **nu am rulat testul manual cerut de task** (DevTools → Network, mișcat sliderul, verificat 0 cereri noi) — n-am avut browser la dispoziție. Merită 2 minute de test real înainte să declari T-08 complet verificat.

## 4. Decizii pierdute la revert, nerescrise

D-008…D-011 originale (COG vs. pre-tiling, evaluare pe adevăr sintetic, verificare mecanică, licența AGPL a ODM) au fost șterse la revert-ul commit-ului `d24a97f` și nu au fost rescrise — deși tot ce descriau chiar s-a implementat între timp (COG la T-06, perechea sintetică la T-03). `D-008` există acum din nou în [[Decizii]], dar cu alt conținut (seed pe disc efemer Render). Pur documentație lipsă, nu blochează codul.

## 5. ~~Curățenie cosmetică~~ — cauza reală reparată (2026-08-21)

Nu era o problemă de fișiere individuale (BOM-ul pe `AGENTS.md`/`CLAUDE.md` era deja intact la verificare) — cauza reală era lipsa unui `.gitattributes` combinată cu `core.autocrlf=true` pe Windows, care făcea ca fiecare checkout pe altă mașină/OS să normalizeze altfel line-ending-urile. Adăugat `.gitattributes` (`* text=auto eol=lf`, rastere/DB explicit binare) și rulat `git add --renormalize .` ca fixul să se aplice și retroactiv, nu doar la clone-uri viitoare.

## 6. ~~Verifică plugin-ul Obsidian Git~~ — confirmat instalat (2026-08-19)

Confirmat de utilizator: Obsidian Git e instalat și funcțional pe mașina principală.

## 7. Stretch, neînceput

- **Faza 1** — ingestie și validare pe date reale de zbor (blur, overlap, GPS EXIF).
- **Faza 2** — fotogrammetrie cu OpenDroneMap (Docker, ore de procesare, licență AGPL de clarificat — vezi [[Intrebari deschise]] Î-05).

---

Reluare rapidă pe altă mașină: `git pull`, `setup-skills.ps1`/`.sh` dacă e prima dată, citește [[Jurnal]] de sus în jos pentru context, apoi ia lista de mai sus de la 1.
