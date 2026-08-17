---
tags: [index, home]
created: 2026-08-17
type: index
---

# CodeVault

Punctul de intrare în vault. Dacă tocmai ai clonat repo-ul pe altă mașină, de aici pornești.

## Proiect activ

- [[Argus Custode]] — nota hub a proiectului de practică
- [[Task-uri de start]] — de aici se lucrează: T-01…T-08, fiecare cu checkul lui
- [[Plan de implementare]] — fazele, ordinea de atac, MVP vs. stretch
- [[Intrebari deschise]] — ce nu știm încă și ce blochează fiecare necunoscută
- [[Decizii]] — de ce am ales ce am ales
- [[Jurnal]] — ce s-a lucrat, pe zile

Verificare, după fiecare task: `python check.py` din rădăcina repo-ului.

## Structura folderelor

| Folder | Ce intră |
|---|---|
| `projects/` | proiecte active, fiecare cu folderul lui |
| `wiki/` | note tehnice durabile: un concept per notă, refolosibile între proiecte |
| `raw/` | capturi brute, nedigerate: exporturi, transcrieri, copy-paste din alte surse |

Regula de trecere: ce e în `raw/` se digeră în `wiki/` sau într-un proiect. Ce rămâne în `raw/` peste o lună probabil nu era util.

## Convenții

- Frontmatter pe fiecare notă: `tags`, `created`, `type`.
- Legături cu wikilinks `[[Titlu notă]]`, nu căi relative.
- Nume de fișiere fără diacritice (compatibilitate între Windows și Linux); diacriticele stau în conținut.
- Notele în română, codul și commit-urile în engleză.
