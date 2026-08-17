---
tags: [argus, concurs, caiet]
created: 2026-08-17
type: nota
---

# Caietul de practică

Proiect: [[Argus Custode]]. Obiectiv declarat: câștigarea concursului de caiete de practică.

## Ideea de bază

Vault-ul **este** caietul. Nu scrii caietul la final din memorie — el se scrie singur dacă [[Jurnal]] e ținut disciplinat pe parcurs. Asta e și motivul pentru care regula 2 din [[Reguli pentru agent executant]] cere output brut lipit: fiecare intrare de jurnal cu o cifră în ea devine, la final, o pagină de caiet cu dovadă.

## Ce diferențiază un caiet câștigător

Majoritatea caietelor descriu ce a făcut studentul. Puține arată **că a măsurat dacă a funcționat**. Diferența e tot ce contează la jurizare.

Ai deja, prin construcție, patru lucruri pe care aproape nimeni nu le are:

1. **O cifră de evaluare reală.** Recall-ul din T-05, măsurat pe adevăr cunoscut. Nu „detectează schimbările", ci „găsește 8 din 10 zone modificate, în top-20 candidați". Asta e limbajul unei lucrări serioase, nu al unui proiect de student.

2. **Metodă de evaluare inventată ca să existe.** Perechea sintetică din T-03 rezolvă o problemă reală: fără date reale, cum demonstrezi că algoritmul funcționează? Răspunsul — îți construiești adevărul — e exact genul de raționament pe care un juriu îl remarcă. Merită o secțiune întreagă în caiet.

3. **Decizii cu motiv, nu cu preferință.** [[Decizii]] conține deja de ce COG și nu pre-tiling, de ce fără Celery, de ce ordinea inversată. Un caiet care explică ce **nu** a construit și de ce arată mai multă maturitate decât unul care enumeră tehnologii.

4. **Constrângeri tratate ca proiectare, nu ca scuze.** N-ai avut date și n-ai știut hardware-ul. În loc să aștepți, ai construit un plan care ocolește ambele necunoscute. Asta e o poveste bună și e adevărată — vezi ordinea din [[Plan de implementare]].

## Structura propusă a caietului

1. Problema și de ce contează (comparație manuală a două zboruri = ore de om)
2. Constrângerile reale de la start și cum au modelat planul
3. Arhitectura, cu deciziile din [[Decizii]] și motivele lor
4. Metoda de evaluare — perechea sintetică cu adevăr cunoscut
5. Rezultate măsurate: recall, timpi, capturi
6. Ce n-a mers și ce s-a învățat din asta
7. Ce urmează, inclusiv perspectiva comercială și problema de licență din [[Intrebari deschise]]

Capitolul 6 nu e opțional. Un caiet fără niciun eșec descris se citește ca un raport de marketing.

## De ținut pe parcurs

- Capturi de ecran la fiecare pas vizibil, în `CodeVault/raw/`, cu dată.
- Cifrele se scriu când se măsoară, nu se reconstituie la final.
- Când un prag se schimbă, se notează **de ce** — traseul deciziilor e mai valoros decât valoarea finală.
