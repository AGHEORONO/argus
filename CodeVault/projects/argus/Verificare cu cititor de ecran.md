---
tags: [argus, accesibilitate, verificare, caiet]
created: 2026-08-30
type: procedura
---

# Verificare cu cititor de ecran — scenariu de parcurs

Proiect: [[Argus Custode]]. Singura verificare de accesibilitate care **nu** s-a făcut niciodată
pe proiectul ăsta, și singura care nu se poate automatiza.

Testele automate (48 Playwright, cu axe-core) prind în jur de **o treime** din problemele WCAG:
o etichetă lipsă, un contrast sub prag, un id duplicat. Nu pot spune dacă ordinea de citire are
sens, dacă un anunț se înțelege, sau dacă cineva chiar poate duce o sarcină la capăt. Doar un om
cu un cititor de ecran poate.

Durata: 20–30 de minute. Se rulează pe `http://127.0.0.1:4173` sau pe aplicația de desktop —
ambele au același DOM.

---

## Pregătire

1. Descarcă **NVDA** de la nvaccess.org (gratuit, open source). Instalează sau rulează portabil.
2. `Ctrl` oprește vorbirea în orice moment. `Insert` este tasta NVDA.
3. Pornește aplicația, apoi NVDA — în ordinea asta, ca pagina să fie deja încărcată.
4. **Închide ochii sau întoarce monitorul** la pașii marcați cu 🙈. Dacă te uiți la ecran,
   testezi altceva decât ai vrut.

---

## A. Orientare — poți spune unde ai ajuns?

| # | Ce faci | Ce trebuie să auzi | Eșec dacă |
|---|---|---|---|
| A1 | Încarci pagina | Numele aplicației, apoi anunțul de detecție finalizată cu numărul de anomalii | Tăcere, sau doar „document" |
| A2 | `Insert`+`F7`, secțiunea Titluri | O listă de titluri care descrie pagina | Un singur titlu, sau niciunul |
| A3 | `Insert`+`F7`, secțiunea Repere | Banner, navigare, principal, complementar | Nu apare niciun reper |
| A4 | `D` repetat (sari între repere) | Treci prin antet, bara de secțiuni, panou, hartă | Sari peste hartă sau peste panou |

---

## B. Bara de secțiuni — decongestionarea

Aici s-a lucrat cel mai mult: raftul avea vreo cincisprezece opriri de `Tab`, acum are una.

| # | Ce faci | Ce trebuie să auzi | Eșec dacă |
|---|---|---|---|
| B1 | `Tab` până ajungi în bară | „Secțiuni de lucru, listă de file, Comparație, filă selectată, 2 din 3" | Se anunță ca butoane separate, nu ca file |
| B2 | `Tab` încă o dată | **Ieși din bară** direct în panou | Mai ai două opriri prin celelalte file |
| B3 | `Shift`+`Tab` înapoi, apoi `↓` | „Anomalii, filă selectată" — și panoul se schimbă **fără** `Enter` | Trebuie `Enter`, sau focusul sare în panou |
| B4 | `↑` de trei ori | Se învârte în cerc: Anomalii → Comparație → Ingestie → Anomalii | Se oprește la capăt |
| B5 | `Home`, apoi `End` | Prima, apoi ultima filă | Nu reacționează |

---

## C. Rezultatul central — poziția anomaliilor 🙈

**Cel mai important test din toată lista.** Harta e un canvas WebGL: pentru cineva care nu vede,
nu există. Dacă poziția anomaliilor nu se poate afla din text, aplicația nu are rezultat.

| # | Ce faci | Ce trebuie să auzi | Eșec dacă |
|---|---|---|---|
| C1 | Mergi pe fila Anomalii | Câte anomalii, și că detaliile sunt în listă | Doar „Anomalii detectate", fără cifre |
| C2 | Activează „Vezi lista completă" | Focusul ajunge pe **titlul** dialogului, nu pe butonul de închidere | Auzi „Închide lista, buton" |
| C3 | `Tab` prin dialog de 25–30 de ori | Nu ajungi niciodată pe un control din spate (filă, slider, casetă) | Auzi „Comparație, filă" — focusul a scăpat |
| C4 | În tabel, `Ctrl`+`Alt`+`→` pe un rând | Zona geografică și coordonatele rostite, nu doar rang și scor | Auzi doar un număr |
| C5 | Activează „Selectează anomalia 2" | Un anunț care spune **care** anomalie și scorul ei | Tăcere — harta s-a mișcat, dar tu nu știi |
| C6 | `Escape` | Dialogul se închide și focusul revine pe butonul de unde ai plecat | Focusul cade pe începutul paginii |

**Întrebarea de control, la final**: fără să te uiți, poți spune câte anomalii sunt și **unde**
e cea mai importantă? Dacă nu, C a picat, indiferent ce spun celelalte rânduri.

---

## D. Comenzile de vizualizare

| # | Ce faci | Ce trebuie să auzi | Eșec dacă |
|---|---|---|---|
| D1 | `Tab` la sliderul de amestec | „Amestec, cursor" plus o **frază** care spune ce se vede, nu doar „50" | Auzi doar un procent |
| D2 | `→` de câteva ori | Fraza se actualizează la fiecare pas | Rămâne la valoarea veche |
| D3 | `Tab` la „Anomalii candidate", `Space` | Starea bifat/nebifat se anunță | Tăcere |
| D4 | Bifează „Schimbări cunoscute" | Apare legenda, iar eticheta hărții se actualizează | Nimic nu se schimbă în text |

---

## E. Ingestia

| # | Ce faci | Ce trebuie să auzi | Eșec dacă |
|---|---|---|---|
| E1 | `Tab` la câmpul ID zbor | Eticheta „ID Zbor" citită împreună cu câmpul | Auzi doar „editare" |
| E2 | `Tab` la zona de fișiere | Instrucțiunea de tragere sau selectare | Doar „buton" |
| E3 | `Tab` la „Încarcă fotografiile" fără fișiere selectate | Butonul e anunțat ca **indisponibil**, plus motivul | E anunțat ca disponibil |
| E4 | Provoacă o eroare (oprește backendul, apasă Încarcă) | Eroarea se anunță singură, fără să cauți | Trebuie să navighezi ca s-o găsești |
| E5 | Apasă „Reîncearcă" | Focusul **nu** se pierde pe body | Următorul `Tab` te duce la începutul paginii |

*E5 verifică un defect reparat pe 2026-08-25 (C1 din [[Probleme si rezolvari]]): butonul își
distrugea propriul focus, fiindcă bannerul care îl conținea se demonta în același commit React.*

---

## F. Reflow — 400% zoom

| # | Ce faci | Ce trebuie să vezi | Eșec dacă |
|---|---|---|---|
| F1 | `Ctrl`+`+` până la 400% | Nicio derulare pe orizontală | Trebuie să derulezi lateral ca să citești |
| F2 | La 400%, bara de secțiuni | Devine orizontală, sus | Iese din ecran |
| F3 | La 400%, banda de comenzi | Iese de pe hartă, nu o acoperă | Acoperă harta |

*F1–F3 sunt acoperite și automat (`reflow.spec.js`), deci aici doar confirmi cu ochii.*

---

## Cum se notează

Un tabel cu trei coloane: **cod** (A1, B3…), **trecut/picat**, **ce s-a auzit de fapt**. Ultima
coloană e cea care contează — „picat" fără citatul a ce s-a auzit nu se poate repara.

Orice a picat se trece în [[De facut]] cu codul lui, ca să nu se piardă.

---

## De reținut înainte de a începe

Rezultatul așteptat nu e „totul trece". Proiectul n-a fost niciodată ascultat, iar prima
ascultare găsește aproape sigur ceva — cel mai probabil în **C**, unde textul e lung și ordinea
contează. Asta nu e un eșec al lucrării; e exact motivul pentru care verificarea există.

Ce se poate spune cinstit la prezentare, dacă verificarea nu s-a făcut încă: *interfața e
construită și verificată automat pentru accesibilitate, cu 48 de teste care includ navigarea de
la tastatură, gestionarea focusului și scanare axe-core; verificarea cu un cititor de ecran real
este pasul următor, iar scenariul de parcurs e scris.* E o poziție mai bună decât o afirmație pe
care n-o poți susține.

---

Legături: [[Argus Custode]] · [[Probleme si rezolvari]] · [[Prezentare generala]] · [[De facut]]
