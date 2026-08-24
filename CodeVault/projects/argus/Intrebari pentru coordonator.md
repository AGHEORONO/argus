---
tags: [argus, intrebari, practica]
created: 2026-08-25
type: intrebari
---

# Întrebări pentru coordonatorul de practică

Proiect: [[Argus Custode]]. De trimis dimineața de 2026-08-26.

Fiecare întrebare de aici blochează ceva concret. Sunt ordonate după cât costă să afli răspunsul târziu, nu după cât de importante par. Cele din secțiunea A schimbă direcția proiectului dacă vin cu întârziere; cele din E sunt bune de știut, dar se pot ocoli.

Versiunea scurtă, de pus în mesaj, e mai jos la [[#Varianta de trimis]]. Restul notei e context pentru discuția de după — de ce contează fiecare și ce se schimbă în funcție de răspuns.

---

## Context de dat înainte de întrebări

Ca să nu pară o listă de cerințe pe gol, merită spus întâi ce există deja. Aplicația e funcțională și publică acum, pe date sintetice:

- Detecție de schimbări între două ortofotoplanuri, cu poligoane și scor de anomalie.
- Hartă interactivă cu slider before/after.
- Validare de poze la ingestie: claritate, GPS din EXIF, suprapunere între cadre consecutive.
- Totul rulează live, fără instalare, pe un link public.

Ce nu există: nicio linie din asta n-a atins vreodată date reale de zbor. De aici vin întrebările.

---

## A. Ce anume livrăm

### Î-A1 — Ce înseamnă „schimbare" pentru firmă?

Construcții noi? Creșterea vegetației? Stocuri de material care se mișcă? Eroziune? Altceva?

**De ce contează cel mai mult**: definiția schimbării decide ce se măsoară în fiecare petic de imagine. Detecția unei clădiri noi și detecția creșterii vegetației cer prelucrări diferite — nu e un parametru de reglat, e altă implementare. Momentan sunt măsuri generice (culoare, varianță locală, gradient), care acoperă rezonabil orice, dar nimic foarte bine.

**Dacă răspunsul întârzie**: se poate lucra mai departe pe generic, dar orice calibrare făcută până atunci e provizorie.

### Î-A2 — Ce livrabil se așteaptă la final?

O aplicație web pe care o folosește cineva din firmă? Un raport cu rezultate? O componentă care se integrează într-un sistem existent? Cod-sursă predat?

**De ce contează**: schimbă complet ce merită lustruit. Dacă e demo de prezentat, contează interfața; dacă e componentă de integrat, contează API-ul și documentația lui; dacă e raport, contează cifrele și metodologia.

### Î-A3 — Există un termen și o formă de prezentare?

Dată, durată, cui se prezintă, ce se așteaptă să se vadă pe ecran.

---

## B. Datele

### Î-B1 — Când vin date reale de zbor, și există deja zboruri arhivate?

**De ce contează**: chiar și un singur zbor vechi, fără pereche, e util imediat — confirmă că formatul, georeferențierea și metadatele se citesc corect. Două zboruri ale aceleiași zone la momente diferite ar debloca validarea reală a detecției.

### Î-B2 — Ce dronă și ce cameră?

**De ce contează, foarte concret**: validarea de la ingestie calculează suprapunerea dintre cadre din poziția GPS, altitudine, distanța focală și lățimea senzorului — toate citite din EXIF. E scrisă și testată pe structura EXIF a unei drone DJI. Dacă zborurile vin de la alt producător, care scrie altfel tag-urile sau nu le scrie deloc, verificarea suprapunerii nu întoarce nimic util și trebuie rescrisă bucata de citire.

Ideal: **o singură poză brută dintr-un zbor real**, ca exemplu. Ar răspunde la această întrebare în cinci minute, mai bine decât orice descriere.

### Î-B3 — Poze brute sau ortofotoplanuri deja procesate?

**De ce contează**: dacă firma are deja ortofotoplanuri gata făcute, întreaga fază de fotogrammetrie (cea mai riscantă și mai costisitoare din tot proiectul) devine inutilă și se poate tăia. Dacă vin doar poze brute, e nevoie de hardware — vezi [[#Î-C1 — Ce hardware e disponibil pentru procesare?]].

### Î-B4 — Ce format și ce sistem de coordonate?

JPEG cu EXIF, sau RAW/DNG? Ortofotoplanurile, dacă există, în ce proiecție sunt (Stereo 70, WGS84, altceva) și în ce format?

### Î-B5 — La ce interval se compară zborurile?

**De ce contează**: la o săptămână distanță, diferențele de lumină și umbre domină semnalul real. La un sezon distanță, vegetația se schimbă natural peste tot și îneacă schimbările care contează cu adevărat. Intervalul decide cât de agresiv e pragul de sensibilitate.

### Î-B6 — Ce suprafață și ce rezoluție?

Câți hectari acoperă un zbor tipic, la ce înălțime, câte poze. Decide dacă procesarea stă pe un laptop sau are nevoie de mașină dedicată.

---

## C. Infrastructura

### Î-C1 — Ce hardware e disponibil pentru procesare?

**De ce contează**: fotogrammetria pe un set de 200 de poze cere procesor multi-core și memorie serioasă, și poate rula ore. Nu merge pe găzduirea gratuită folosită acum pentru demo.

### Î-C2 — Unde rulează varianta finală?

Pe infrastructura firmei, în cloud, sau local pe o stație? Dacă e vorba de infrastructura firmei, ce restricții există (rețea închisă, aprobare de software, sistem de operare impus).

---

## D. Juridic și confidențialitate

### Î-D1 — Licența AGPL a OpenDroneMap e acceptabilă?

Motorul de fotogrammetrie luat în calcul, OpenDroneMap, e sub licență AGPL. Aceasta extinde obligația de a pune la dispoziție codul-sursă și în cazul software-ului accesibil prin rețea, nu doar al celui distribuit ca fișier.

**De ce contează**: dacă răspunsul e „nu", faza de fotogrammetrie are nevoie de alt motor sau de o rulare complet separată de produs. Planul curent îl folosește ca proces izolat, care doar produce fișiere — modelul care ridică cele mai puține întrebări — dar asta nu înlocuiește o confirmare de la cineva care poate să o dea.

### Î-D2 — Datele de zbor sunt confidențiale?

**De ce contează**: acum totul e public — cod, note, demo — pe date sintetice, iar backend-ul nu are autentificare. În momentul în care intră imagini reale ale unor amplasamente ale firmei, asta trebuie schimbat înainte, nu după. Bun de știut dacă e nevoie și de un acord de confidențialitate.

---

## E. Utilizatorii

### Î-E1 — Cine folosește efectiv aplicația?

Ingineri care știu ce e un ortofotoplan, sau oameni din administrativ? Decide cât context trebuie explicat în interfață.

### Î-E2 — Există cerințe de accesibilitate?

**De ce întreb**: dacă beneficiarul final e o instituție publică sau un proiect cu finanțare publică, se aplică cerințe legale de accesibilitate digitală (standardul european EN 301 549). E mult mai ieftin de respectat din construcție decât adăugat la final. Interfața e deja proiectată în direcția asta — funcționează integral de la tastatură — dar dacă e o cerință formală, se schimbă și ce trebuie documentat.

### Î-E3 — Câți oameni, și simultan?

Decide dacă e nevoie de conturi, de coadă de procesare și de bază de date serioasă, sau dacă varianta simplă de acum e suficientă.

---

## Varianta de trimis

Textul de mai jos e cel care se poate copia direct într-un mesaj. Restul notei rămâne pentru discuția de după.

> Bună ziua,
>
> Am ajuns într-un punct în care aplicația e funcțională cap-coadă pe date de test: detectează schimbări între două ortofotoplanuri ale aceleiași zone, le afișează pe hartă cu comparație before/after, și verifică automat calitatea pozelor la încărcare. Rulează pe un link public, fără instalare.
>
> Ca să merg mai departe pe date reale, aș avea nevoie de câteva clarificări:
>
> 1. **Ce înseamnă „schimbare"** pentru dumneavoastră — construcții noi, vegetație, stocuri de material, eroziune? De asta depinde direct ce anume caută algoritmul.
> 2. **Când ar putea veni date reale de zbor**, și există zboruri mai vechi, arhivate?
> 3. **Ce dronă și ce cameră** se folosesc? Dacă se poate, **o singură poză brută dintr-un zbor real** mi-ar răspunde la mai multe întrebări tehnice deodată.
> 4. Primim **poze brute sau ortofotoplanuri deja procesate**? Dacă există deja ortofotoplanuri, se poate scurta considerabil partea cea mai grea a proiectului.
> 5. **Ce hardware e disponibil** pentru procesare? Reconstrucția din poze cere resurse care nu încap pe găzduirea gratuită folosită acum pentru demo.
> 6. **Ce livrabil așteptați la final** — aplicație de folosit, raport cu rezultate, sau componentă de integrat în ceva existent?
> 7. **Sunt datele de zbor confidențiale?** Momentan totul e public pentru că sunt date sintetice; dacă intră imagini reale, schimb asta din timp.
>
> Pot continua și fără răspunsuri imediate — lucrez mai departe pe date publice — dar primele trei ar schimba priorități, deci cu cât vin mai devreme, cu atât mai puțin lucru se face degeaba.
>
> Mulțumesc,

---

Legături: [[Intrebari deschise]] (întrebările tehnice deschise, formulate pentru mine, nu pentru firmă), [[Plan de implementare]], [[Decizii]], [[De facut]].
