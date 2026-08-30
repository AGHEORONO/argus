---
tags: [argus, todo]
created: 2026-08-17
type: todo
---

# De făcut

Proiect: [[Argus Custode]]. Tot ce a rămas deschis la finalul sesiunii de azi (2026-08-17), ca să nu se piardă până la reluare — pe orice mașină. Ordonate aproximativ după cât de mult contează. La 2026-08-25: Faza 1 e implementată; rămân deschise punctul 7 (Faza 2, ODM) și punctul 8 (harta fără echivalent textual).

## 1. ~~Faza 7 — deployment real~~ — LIVE, verificat independent (2026-08-21)

Ambele componente sunt public accesibile, fără login, verificate cu `curl`/`vercel curl` din afara conversației (nu doar status API):

- **Backend**: `https://argus-backend-yw3h.onrender.com` (Render, free tier). Trei eșecuri reale rezolvate pe drum — vezi [[Jurnal]] 2026-08-21: Python 3.11→3.12 în `Dockerfile` (numpy n-avea wheel), apoi două runde de OOM (exit 137) reparate prin streaming pe ferestre (`rasterio.windows.Window`) în `provision.py`/`detect.py` și downsampling la 3000px pe latura lungă.
- **Frontend**: `https://argus-agheoronos-projects.vercel.app` (Vercel). SSO protection era activă implicit pe tot proiectul (inclusiv producție) — dezactivată explicit cu acordul utilizatorului, altfel linkul nu era deschis public.

De reținut pentru viitor: `VITE_API_BASE` trebuie adăugat separat pe Production **și** Preview în Vercel — CLI-ul nu propagă automat între medii.

## 2. ~~Recall T-05~~ — 4/4, confirmat pe datele curente de producție (2026-08-21)

Traseu complet: 3/4 (17 aug, neverificat/nereprodus) → 2/4 (19 aug, verificare independentă pe desktop, `top_n=20`) → 3/4 (`top_n=50`, tot fără zona de vegetație) → **4/4** (21 aug, după downsampling-ul din D-010 — zona de vegetație a devenit detectabilă la rezoluția redusă, efect secundar neplanificat). Verificat riguros cu `detect_changes()` la parametrii impliciți din cod, pe fișierele exact ca în producție. Nu s-a mai investigat *de ce* rezoluția mai mică ajută (posibil netezire/reducere zgomot din resampling) — funcțional, e rezolvat.

## 3. ~~T-08 — sliderul~~ — verificat mecanic, 0 cereri (2026-08-25)

Testul cerut de task s-a făcut, doar nu din DevTools: extensia Chrome nu era conectată, așa că a rulat Playwright headless pe frontend-ul de producție, numărând cererile programatic. Drag realist (41 de evenimente de mișcare, 8 secunde, slider 0.5 → 0.95): **0 cereri de rețea noi**, dintre care 0 `/tiles/` și 0 XHR/fetch. Cele 16 cereri `/tiles/` de la încărcare confirmă că harta era vie în timpul drag-ului. Vezi [[Jurnal]] 2026-08-25.

## 4. ~~Decizii pierdute la revert~~ — rescrise ca D-012…D-015 (2026-08-25)

Rescrise ca **D-012…D-015** în [[Decizii]] (sloturile D-008…D-011 fuseseră între timp refolosite pentru alte decizii, deci nu s-au atins). Fiecare intrare e marcată explicit ca rescrisă după revert-ul `d24a97f`.

Descoperit pe parcurs: și `Î-05` (licența AGPL a ODM) fusese pierdut la același revert, deși era referențiat din trei fișiere. Adăugat în [[Intrebari deschise]].

## 5. ~~Curățenie cosmetică~~ — cauza reală reparată (2026-08-21)

Nu era o problemă de fișiere individuale (BOM-ul pe `AGENTS.md`/`CLAUDE.md` era deja intact la verificare) — cauza reală era lipsa unui `.gitattributes` combinată cu `core.autocrlf=true` pe Windows, care făcea ca fiecare checkout pe altă mașină/OS să normalizeze altfel line-ending-urile. Adăugat `.gitattributes` (`* text=auto eol=lf`, rastere/DB explicit binare) și rulat `git add --renormalize .` ca fixul să se aplice și retroactiv, nu doar la clone-uri viitoare.

## 6. ~~Verifică plugin-ul Obsidian Git~~ — confirmat instalat (2026-08-19)

Confirmat de utilizator: Obsidian Git e instalat și funcțional pe mașina principală.

## 7. Stretch

- **Faza 1** — ~~ingestie și validare~~ **implementată** (T-09, T-10, T-11, 2026-08-25): validare de blur, GPS EXIF și suprapunere, expusă prin API și prin panou de frontend operabil integral de la tastatură. **Rămâne**: n-a rulat niciodată pe poze reale de dronă — EXIF-ul e scris de noi. Vezi [[Decizii]] D-016.
- **Faza 2** — fotogrammetrie cu OpenDroneMap (Docker, ore de procesare, licență AGPL de clarificat — vezi [[Intrebari deschise]] Î-05).

## 8b. ~~Nu exista niciun test de frontend~~ — 45 de teste in CI (2026-08-30)

Toate scripturile de verificare de pana acum erau de unica folosinta si nu mai existau in
repo, deci munca de accesibilitate era nereproductibila si CI-ul verifica doar ca frontendul
compileaza. Acum: `app/frontend/tests-e2e/` (tastatura, focus, dialog, reflow, echivalentul
textual al hartii, axe-core) plus `tests/test_api_contract.py` care tine backendul simulat
lipit de cel real. Rulate la fiecare push. Vezi [[Jurnal]] 2026-08-30.

**Ramane netestat**: nicio trecere cu un cititor de ecran real (NVDA/VoiceOver). Axe prinde
vreo treime din problemele WCAG si niciuna dintre cele de ordine si sens.

## 8. Harta n-are echivalent textual (nou, 2026-08-25)

Ieșit la revizuirea de accesibilitate a Fazei 1, dar e o problemă mai veche și mai mare decât panoul de ingestie: `<div id="map">` n-are nume accesibil, n-are rol și n-are nicio alternativă textuală. Poziția geografică a fiecărei anomalii — adică rezultatul central al aplicației — e disponibilă exclusiv vizual. Lista de candidați dă rang și scor, niciodată locația.

Cineva care nu vede harta poate parcurge tot fluxul de ingestie, dar nu poate consuma niciun rezultat de detecție. Netratat, doar înregistrat.

---

## Pentru caietul de practică

Sinteza e scrisă în două note separate, ca să nu trebuiască parcurs [[Jurnal]] de sus în jos:

- [[Prezentare generala]] — ce face aplicația, arhitectura, cifrele, și ce NU s-a făcut
- [[Probleme si rezolvari]] — fiecare problemă întâlnită, cu simptom, cauză, reparație și ce a
  rămas de învățat
- [[Verificare cu cititor de ecran]] — de rulat cu NVDA, 20-30 de minute; e singurul lucru din
  accesibilitate care n-a fost verificat niciodată

---

## Cum pornești aplicația local

`.\start-local.ps1` dintr-un terminal normal. Pornește backendul, construiește frontendul cu `VITE_API_BASE` către el, îl servește pe `http://127.0.0.1:4173`, și oprește tot la `Ctrl+C`.

De rulat dintr-un terminal propriu, nu dintr-o sesiune de agent: procesele pornite de un agent sunt oprite când se încheie sesiunea lui, ceea ce face imposibilă testarea în ritm propriu.

---

Reluare rapidă pe altă mașină: `git pull`, `setup-skills.ps1`/`.sh` dacă e prima dată, citește [[Jurnal]] de sus în jos pentru context, apoi ia lista de mai sus de la 1.
