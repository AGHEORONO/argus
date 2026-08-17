---
tags: [argus, jurnal]
created: 2026-08-17
type: jurnal
---

# Jurnal de lucru

Proiect: [[Argus Custode]]. Intrare nouă sus. Scurt: ce s-a făcut, ce s-a blocat, ce urmează. Fără proză.

## 2026-08-17 (3)

**Făcut**: adăugată regula de delegare către `agy`/Gemini în `CLAUDE.md`/`AGENTS.md` (rădăcină + copiile din `CodeVault`): execuție pe Gemini (`gemini-3.7-flash-high`), fallback la Claude direct când Gemini nu face față, scop limitat strict la acest proiect (nu afectează Claude Code în general și nu afectează Antigravity IDE deschis direct).

**Blocaje**: incident — un test scurt cu `agy --dangerously-skip-permissions` a găsit modificări necomise în working tree și a decis singur, pe baza regulii vechi „commit ca dovadă", să comită și să dea push la ~500 de linii nesolicitate direct pe `origin/main` (commit `d24a97f`). Revertat (`f821d21`), conținutul era legitim dar push-ul nu fusese aprobat. Regulă nouă: `agy` nu mai atinge git, doar Claude comite/pushuiește, după confirmare.

**Urmează**: reluat de unde a rămas planul — [[Task-uri de start]] au fost pierdute la revert; de rescris sau reluat din `Plan de implementare` înainte de T-01.

---

## 2026-08-17

**Făcut**: setat repo-ul și vault-ul. Stabilit numele, structura, stack-ul, ordinea de execuție. Scris [[Plan de implementare]], [[Decizii]], [[Intrebari deschise]].

**Blocaje**: niciunul care oprește lucrul. Hardware-ul de procesare și datele de zbor sunt necunoscute, dar planul le ocolește prin ordinea aleasă.

**Urmează**:
1. Instalat plugin Obsidian Git pe ambele mașini (PC + laptop).
2. Descărcat un ortofotoplan public și construită perechea sintetică before/after cu schimbări injectate.
3. Început faza 4: features per patch + Isolation Forest.
