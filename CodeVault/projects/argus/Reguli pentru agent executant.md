---
tags: [argus, reguli, executie]
created: 2026-08-17
type: reguli
---

# Reguli pentru agent executant

Proiect: [[Argus Custode]]. Contractul pe care îl respectă modelul care execută [[Task-uri de start]] — Sonnet, Gemini Flash sau orice altceva rapid și ieftin. Deciziile de arhitectură sunt deja luate în [[Decizii]]; aici nu se redeschid.

## De ce arată așa

Un model ieftin nu devine fiabil pentru că i-ai scris instrucțiuni mai frumoase. Devine fiabil când fiecare pas are o verificare care pică zgomotos și când nu i se cere să decidă nimic. Regulile de mai jos există ca să mute judecata din model în checkuri.

## Regulile

1. **Un task pe rând**, în ordinea din [[Task-uri de start]]. Nu sări, nu combina, nu începe T-05 pentru că T-04 „e clar oricum".

2. **Nu marca nimic terminat fără output de check lipit în [[Jurnal]].** Nu „am rulat testele și trec" — output-ul brut, copiat. Un task fără output lipit se consideră nefăcut.

3. **`python check.py` după fiecare task**, pe lângă checkul specific. Dacă pică, repari înainte să continui.

4. **Nu adăuga ce nu e cerut.** Fără clase de configurare, fără straturi de abstractizare, fără endpoint-uri „că oricum o să avem nevoie". Dacă un task cere o funcție, livrezi o funcție.

5. **Nu instala dependințe care nu sunt scrise în task.** Dacă pare că lipsește ceva, e semn că soluția aleasă e greșită, nu că lipsește o bibliotecă.

6. **Pragurile sunt parametri, nu constante.** `patch`, `contamination`, pragurile de scor — argumente cu valoare implicită, niciodată numere îngropate în cod. Se calibrează pe date reale mai târziu.

7. **Dacă un check pică de trei ori, oprește-te.** Scrie în [[Jurnal]] ce ai încercat și de ce a picat. Nu improviza o soluție ocolitoare, nu slăbi pragul din test ca să treacă. **Slăbirea unui test ca să treacă e cel mai grav lucru care se poate întâmpla în proiectul ăsta** — transformă măsurătoarea în minciună, iar cifra măsurată e exact ce vinde proiectul la concurs.

8. **Un commit per task**, mesaj `T-0X: ce s-a făcut`. Fără commit-uri mari care amestecă taskuri.

9. **Nu atinge**: `.gitignore` (regula cu `data/`), istoricul git, credențiale, token-uri, `.obsidian/`. Imaginile și rasterele nu intră niciodată în git — odată intrate, nu mai ies ieftin.

10. **Când scrii în [[Jurnal]]**: ce s-a făcut, cifrele măsurate, ce a picat. Fără proză, fără „am implementat cu succes".

## Ce raportează la final

Pentru verificarea finală (Opus), un rezumat cu:
- ce taskuri au trecut, cu output-ul checkurilor
- cifrele măsurate: recall în T-05, timpii din T-04 și T-06
- ce s-a blocat și la ce pas
- orice loc unde a fost nevoie de o decizie care nu era în task — astea sunt exact punctele de verificat

## Ce verifică Opus la final

Nu că „merge" — că **cifrele sunt reale**. Concret: că testele chiar testează ce pretind, că pragurile n-au fost coborâte ca să treacă, că nu s-au strecurat abstracții inutile, și că adevărul din `truth.geojson` nu s-a scurs cumva în antrenare (dacă modelul vede unde sunt schimbările, recall-ul de 0.9 nu înseamnă nimic).
