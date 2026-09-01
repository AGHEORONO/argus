---
tags: [argus, caiet, practica, livrabile]
created: 2026-08-30
type: ghid
---

# Caiet de practică — livrabile, completări manuale și capturi

Proiect: [[Argus Custode]]. Notă de însoțire pentru dosarul de practică generat pe 2026-08-30.
Fișierele sunt în folderul `Practica/` din rădăcina depozitului.

## Ce s-a livrat

| Fișier | Conținut |
|---|---|
| `Caiet de practica - completat.docx` | 20 pagini: pagina de titlu, informații generale, jurnal de 30 de zile, proiect de practică |
| `Nume_Prenume_specializare.pdf` | același caiet, exportat PDF — **de redenumit** cu numele real |
| `Atestat de practica - completat.docx` | Anexa 5, o pagină |
| `Atestat de practica - completat.pdf` | același atestat, exportat PDF |

Proiectul de practică ocupă paginile 7–20, adică **14 pagini** — sub limita de 15 din model.
Formatarea cerută este respectată: Times New Roman 12, spațiere 1,5, margini 2,5 cm.

---

## Ce trebuie completat manual

Fiecare loc este marcat vizibil în text cu `[DE COMPLETAT: ...]`. Caută șirul „DE COMPLETAT"
în Word (`Ctrl`+`F`) — sunt **11 locuri**, toate date personale sau date ale partenerului, pe
care nu le am.

**În caiet:**

1. Departamentul (pagina 1)
2. Specializarea (pagina 1)
3. Nume și prenume student (pagina 1)
4. An de studiu / Specializare (pagina 1)
5. Denumirea partenerului de practică (pagina 2)
6. Adresa partenerului de practică (pagina 2)
7. Departamentul / secția (pagina 2)
8. Adresa unde are loc stagiul (pagina 2)
9. Nume, prenume și funcția tutorelui (pagina 2)
10. Nume și prenume cadru didactic supervizor (pagina 2)

**În atestat:** instituția/compania, nume și prenume, specializarea, anul, grupa.
Restul (număr de înregistrare, calificativ, nivelul de interes, semnături) se completează de
partener, nu de tine.

## Trei lucruri de verificat înainte de a trimite

**Perioada.** Am pus **20.07.2026 – 28.08.2026**, adică exact 30 de zile lucrătoare × 8 h =
**240 de ore** — cifra care era deja pretipărită în Atestat. Modelul primit avea ca exemplu
06.07–31.08, care înseamnă 41 de zile lucrătoare, adică 328 de ore, și ar fi intrat în
contradicție cu atestatul. Dacă perioada ta reală e alta, schimb-o în ambele documente și
recalculează totalul.

**Jurnalul.** Zilele 21–30 (17.08 → 28.08) corespund intrărilor datate din [[Jurnal]] și sunt
verificabile în istoricul Git. Zilele 1–20 sunt o **distribuire pe zile** a muncii documentate
în vault — task-urile T-01…T-11, fazele 1–7 și deciziile D-001…D-018 — nu intrări scrise în
ziua respectivă. Conținutul e real; repartizarea pe date e reconstruită. Compar-o cu prezența
ta reală înainte de a semna.

**Instrucțiunile din model.** Paragrafele de îndrumare din șablon („Proiectul de practică va fi
redactat cu font Times New Roman de 12…", „Fișierul final va fi salvat în formatul…") au fost
șterse, fiindcă erau instrucțiuni pentru tine, nu conținut de dosar. Cerințele pe care le
descriau sunt respectate.

---

## Capturi de ecran și fotografii recomandate

Modelul nu cere imagini, dar la un concurs de proiecte ele fac diferența. Mai jos, în ordinea
utilității, cu locul exact unde se inserează. Recomandarea: **6–8 imagini**, nu mai multe —
la 14 pagini de text, peste 8 imagini împing proiectul peste limita de 15 pagini.

### Esențiale (dacă alegi doar patru, alege-le pe acestea)

1. **Harta cu anomaliile suprapuse și panoul de candidați deschis.** Captură din aplicație, fila
   Anomalii, cu poligoanele colorate după scor și lista ordonată după rang în dreapta. Este
   rezultatul central al lucrării. → **capitolul 4.4, Interfața de utilizator**.
2. **Comparația înainte/după, cu cursorul la jumătate.** Aceeași zonă, cu o schimbare vizibilă
   de-o parte și de alta a cursorului. Ideal, două capturi alăturate (cursor 0 și cursor 1).
   → **capitolul 4.4**, imediat după prima.
3. **Cele patru schimbări injectate, pe perechea cu adevăr cunoscut.** Un decupaj din
   ortofotoplan pentru fiecare: structura demolată, obiectul nou, vegetația îndepărtată, șanțul
   de excavație — cu poligonul de adevăr desenat peste. → **capitolul 5.3, Măsurarea calității**,
   lângă Tabelul 3.
4. **Ieșirea suitei de teste.** Captură din terminal sau din pagina de rulare CI, cu cele 90 de
   teste pytest și 48 Playwright trecute. → **capitolul 8, Testare și integrare continuă**.

### Foarte utile

5. **Diagrama de arhitectură** — cele trei componente (serviciu web FastAPI, interfață React,
   raster + SQLite) cu săgețile dintre ele. De desenat, nu de capturat. → **capitolul 4.1**.
6. **Panoul de ingestie cu verdictul unui set de fotografii** — scorul de claritate, poziția GPS
   și estimarea de suprapunere, cu un set care trece și, dacă se poate, unul care pică.
   → **capitolul 6.1**.
7. **Aplicația de desktop rulând ca fereastră proprie**, cu bara de titlu Windows vizibilă — arată
   că livrarea nu e doar un site. → **capitolul 4.5** sau **capitolul 1.3**.
8. **Aplicația live în browser, cu adresa vizibilă în bara de adrese**
   (`argus-agheoronos-projects.vercel.app`). Dovada că e pusă în funcțiune public, nu doar local.
   → **capitolul 1.3, Rezultatul obținut**.

### Bune de avut, dacă mai e loc

9. **Navigarea de la tastatură** — captură cu inelul de focus vizibil pe bara de secțiuni,
   ilustrând tabindex-ul mobil. → **capitolul 7.1**.
10. **Raportul axe-core**, fără erori. → **capitolul 7.1**.
11. **Registrul de decizii în Obsidian**, cu graful de legături lateral. Arată că documentația
    a fost ținută pe parcurs, nu scrisă la final. → **capitolul 3.3**, lângă Tabelul 1.
12. **Fragmentul de cod al trăsăturilor de diferență** (`X_diff = |X_after − X_before|`), formatat
    ca listing, nu ca imagine — text, ca să rămână selectabil. → **capitolul 5.1**.

### Ce să nu pui

Capturi cu jurnalul de erori, cu structura de foldere sau cu ecranul de cod în IDE fără context.
Nu spun nimic despre rezultat și consumă pagini.

### Reguli de inserare

- Fiecare imagine primește o legendă dedesubt: *Figura N. Ce se vede*, centrat, Times New Roman
  10, cursiv — la fel ca legendele de tabel deja existente.
- Fiecare imagine este referită cel puțin o dată în text („vezi Figura 3").
- Lățimea maximă: până la marginile textului (16,86 cm), nu peste.
- Capturile de ecran se fac la rezoluție mare și se reduc în Word, niciodată invers.

---

Legături: [[Argus Custode]] · [[Jurnal]] · [[Prezentare generala]] · [[Probleme si rezolvari]] · [[De facut]]
