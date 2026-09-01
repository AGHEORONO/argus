# Capturi pentru proiectul de practică — legende și locul lor

Actualizat 2026-08-30, după ce ai trimis cele trei capturi care cereau calculatorul tău.
Setul e acum complet: 15 fișiere, 13 figuri.

> **Ce s-a făcut între timp.** Șapte dintre imagini sunt deja puse, ca **anexă la finalul
> caietului**, în `Caiet de practica - RECUPERAT cu anexa.docx` (paginile 21–25). Modelul de la
> Politehnica cere explicit asta: *„Acesta va fi însoțit de câteva instantanee (poze) din
> perioada practicii."* Tabelul de mai jos rămâne valabil dacă vrei, în plus, să pui figuri și
> în interiorul capitolelor — dar atenție, proiectul e la 14 din maximum 15 pagini, deci nu
> încape mare lucru inline.

Sub fiecare imagine se pune legenda de mai jos, centrată, Times New Roman, cursiv — la fel ca
legendele de tabel deja existente în caiet. Fiecare figură se referă cel puțin o dată în text
(„vezi Figura 3").

Lățimea maximă: până la marginile textului, **16,0 cm** (A4 cu margini de 2,5 cm; în anexă am
folosit 15,5 cm ca să rămână puțin aer).

## Ce se pune și unde

Numerotarea de mai jos e în ordinea apariției în text, deci asta e ordinea finală. Numele
fișierelor păstrează gruparea veche pe subiecte, de aceea nu coincid cu numerele figurilor.

| Nr. | Fișier | Capitolul | Legenda |
|---|---|---|---|
| 1 | Figura 10 | 1.3 Rezultatul obținut | *Figura 1. Aplicația în funcțiune la adresa publică, fila Comparație.* |
| 2 | Figura 12 | 3.3, lângă Tabelul 1 | *Figura 2. Registrul de decizii din vault-ul de documentație și graful legăturilor dintre note.* |
| 3 | Figura 6 | 4.1 Arhitectura | *Figura 3. Cele trei componente ale sistemului și fluxurile dintre ele.* |
| 4 | Figura 1 | 4.4 Interfața de utilizator | *Figura 4. Harta cu anomaliile suprapuse, colorate după scor, și panoul de candidați ordonat după rang.* |
| 5 | Figura 3a + 3b | 4.4, imediat după | *Figura 5. Aceeași zonă înainte și după: containerul albastru apare numai în ortofotoplanul „după", în interiorul poligonului de anomalie.* |
| 6 | Figura 3c | opțional, lângă 3a/3b | *Figura 6. Cursorul de tranziție la jumătate, cu cele două ortofotoplanuri alăturate.* |
| 7 | Figura 11 | 4.5 Împachetare și livrare | *Figura 7. Aplicația de desktop pentru Windows, rulând ca fereastră proprie, cu interfața servită din același proces.* |
| 8 | Figura 2 | 5.3 Măsurarea calității | *Figura 8. Lista completă de anomalii, cu coloana care leagă fiecare candidat de schimbarea cunoscută pe care o acoperă.* |
| 9 | Figura 4 | 5.3, lângă Tabelul 3 | *Figura 9. Cele patru schimbări injectate. Pentru fiecare: decupajul înainte, decupajul după și amplitudinea diferenței, cu poligonul de adevăr desenat peste.* |
| 10 | Figura 7a + 7b | 6.1 Ingestia | *Figura 10. Verdictul de ingestie pentru un set de fotografii acceptat și pentru unul respins.* |
| 11 | Figura 8 | 7.1 Accesibilitate | *Figura 11. Inelul de focus vizibil pe bara de file, la navigarea de la tastatură.* |
| 12 | Figura 5 | 8 Testare și integrare continuă | *Figura 12. Rularea suitei de teste: 86 de teste pytest trecute și 48 de teste Playwright.* |

**Figura 9** (fișierul „aplicatia intreaga, fila Comparatie") a rămas nefolosită: arată același
lucru ca Figura 1 din tabel, dar fără cadrul browserului. Ai două opțiuni — fie o folosești în
4.4 dacă vrei o vedere de ansamblu curată a interfeței, fie o lași deoparte. Captura ta cu
adresa vizibilă e mai valoroasă în 1.3, fiindcă dovedește că aplicația chiar e publică.

**Dacă alegi doar patru:** Figura 1 (aplicația live), Figura 4 (harta cu anomalii), Figura 5
(perechea înainte/după) și Figura 9 (cele patru schimbări injectate). Renumerotează.

## Observații pe capturile tale

Toate trei sunt bune și se pot pune ca atare. Două lucruri, dacă ai chef să le refaci — nu e
obligatoriu:

- Cele trei capturi sunt la 1x (≈1850 px lățime), ceea ce la 16,86 cm dă în jur de 275 dpi.
  Suficient pentru tipar, doar puțin mai moale decât restul, care sunt la rezoluție dublă.
- În captura din Obsidian, nota **Decizii** e evidențiată în graf, dar nu e deschisă în editor.
  Dacă o deschizi în panoul din stânga și lași graful în dreapta, se vede și conținutul
  deciziilor, nu doar că există. Argumentul „documentația a fost ținută pe parcurs" e mai
  convingător așa.

## Trei lucruri de verificat în text

**Adâncimea de regăsire: 10 sau 16?** Testul de referință (`test_recall_benchmark.py`, seed
20260826) dă rangurile 10, 1, 9, 2 — deci **adâncime maximă 10**, cifra din proiect. Zborul
demonstrativ salvat în aplicație a fost calculat cu altă rulare și afișează pe ecran
**„toate în primele 16"**. Ambele sunt adevărate, dar dacă pui Figura 4 lângă fraza cu „primele
10", cine citește vede o nepotrivire. Cea mai curată rezolvare: în text spune explicit că
cifra vine din testul de referință cu seed-ul 20260826, iar rangul depinde de rulare.

**Numărul de teste.** Colectate: **91** cu pytest (86 trec aici, 1 e sărit, 4 rulează numai pe
Windows fiindcă pornesc executabilul) plus **48** Playwright. Dacă în proiect scrie 90, se poate
corecta la 91.

**Numărul de rute HTTP.** Sunt **21**, nu 13: 10 în `main.py`, 3 în `tiles.py` și 8 în
`sites.py`. Numărul 13 din text a omis routerul de situri și comparații.

Raportul axe-core fără erori nu l-am putut genera aici — rularea cere descărcarea unui browser
care e blocată în mediul meu. Testul `axe.spec.js` există și trece la tine, deci poți scoate
captura direct dacă vrei să o adaugi la 7.1.

---

Legături: [[Argus Custode]] · [[Caiet de practica - livrabile]]
