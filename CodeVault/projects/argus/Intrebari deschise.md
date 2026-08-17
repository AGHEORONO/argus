---
tags: [argus, intrebari, blocante]
created: 2026-08-17
type: intrebari
---

# Întrebări deschise

Proiect: [[Argus Custode]]. Fiecare necunoscută cu faza pe care o atinge și cu ce facem dacă rămâne fără răspuns. Regula: nicio întrebare deschisă nu are voie să blocheze lucrul — dacă blochează, îi scriem fallback și mergem mai departe.

## Î-01 — Ce hardware avem pentru fotogrammetrie?

**Blochează**: Faza 2 (ODM).
**De ce contează**: ODM cere CPU multi-core și RAM serios; un set de 200 de poze poate rula ore. Nu merge pe free tier Render/Vercel.
**De aflat**: RAM și CPU pe mașina de lucru; dacă firma sau facultatea dă acces la un server.
**Fallback**: faza 2 rămâne ultima și opțională. Lucrăm pe ortofotoplanuri gata-făcute; aplicația e completă fără ea.

## Î-02 — Când vin datele reale de zbor?

**Blochează**: Fazele 1 și 2 pe date reale.
**De aflat**: dacă există acces la dronă, când se fac zborurile, dacă se pot face **două zboruri peste aceeași zonă** la distanță de timp — fără asta nu există caz de test real pentru faza 4.
**Fallback**: set demo public ODM + pereche sintetică cu schimbări injectate manual (adevăr cunoscut, deci măsurabil). Vezi [[Plan de implementare]].
**De reținut**: două zboruri peste aceeași zonă e cerința reală, nu „poze de dronă" în general. Merită cerut explicit, devreme.

## Î-03 — Care sunt cerințele oficiale ale firmei?

**Blochează**: prioritizarea fazelor, posibil scopul întreg.
**De aflat**: ce livrabil așteaptă efectiv, ce zone/tip de teren, ce înseamnă „schimbare" pentru ei (construcții? vegetație? stocuri de material? eroziune?).
**De ce contează cel mai mult**: definiția schimbării decide ce features extragi în faza 4. Detecția de construcții nouă și detecția de creștere a vegetației cer prelucrări diferite.
**Fallback**: fazele sunt scrise independent, deci reordonarea costă puțin. Până vin cerințele, features generice (culoare, textură, gradient) acoperă rezonabil orice tip de schimbare.

## Î-04 — La ce interval se compară zborurile?

**Blochează**: calibrarea pragului în faza 4.
**De ce contează**: la o săptămână distanță, diferențele de iluminare și umbre domină semnalul real. La un sezon distanță, vegetația se schimbă natural peste tot și înecă schimbările care contează.
**Fallback**: prag și dimensiune de patch reglabile, nu constante în cod. Se calibrează când apar date reale.

---

Când o întrebare primește răspuns, mut-o în [[Decizii]] ca decizie, cu data, și șterge-o de aici.
