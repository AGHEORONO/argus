# AGENTS.md / CLAUDE.md — Practica & Obsidian Vault Workspace

## Project Context
- **Workspace**: `Practica`
- **Obsidian Vault**: `CodeVault`
- **Version Control**: Git / GitHub

## Operating Rules & Workflow
1. **Obsidian Integration**:
   - Create, edit, and organize notes as standard Markdown (`.md`) files inside the vault.
   - Use Obsidian conventions: frontmatter metadata (`tags`, `created`, `type`), wikilinks (`[[Note Name]]`), and clean folder structures (`wiki/`, `raw/`, `projects/`).
   - Preserve `.obsidian/` configuration and maintain valid link structures.
2. **Git & Recovery-First (Post-Karpathy)**:
   - Act by default for reversible, local work.
   - Verify before claiming tasks are done.
   - Escalate before touching sensitive keys, credentials, or destructive git operations.
   - Keep GitHub as the remote source of truth.
3. **Ponytail (Lazy Senior Dev Mode)**:
   - Avoid bloated abstractions and unnecessary code.
   - Prefer stdlib, native platform features, and simplest working implementations.

---

## Required Agent Skills & Auto-Installation

If running on a **new device / machine** where skills are not yet installed, execute `setup-skills.ps1` (Windows) or `setup-skills.sh` (macOS/Linux) or install via the repositories below:

### 1. AI Second Brain
- **Repository**: `https://github.com/charlie947/ai-second-brain`
- **Targets**: `~/.claude/skills/ai-second-brain`, `~/.agents/skills/ai-second-brain`

### 2. Post-Karpathy Agentic Engineering
- **Repository**: `https://github.com/ramsani/Post-Karpathy-Agentic-Engineering`
- **Targets**: `~/.claude/skills/post-karpathy`, `~/.agents/skills/post-karpathy`

### 3. Ponytail (Lazy Senior Dev Suite)
- **Repository**: `https://github.com/dietrichgebert/ponytail`
- **Targets**: `~/.claude/skills/ponytail*`, `~/.agents/skills/ponytail*`, `~/.agents/rules/ponytail.md`
- **Bundled Skills**: `ponytail`, `ponytail-review`, `ponytail-audit`, `ponytail-debt`, `ponytail-gain`, `ponytail-help`

---

## Delegation to Gemini (agy / Antigravity CLI)

Scope: **this project only**, both machines (desktop now, laptop in Timișoara later). Opening Claude Code anywhere else, or opening Antigravity IDE directly, is unaffected — nothing here changes their defaults, only how Claude behaves inside this folder.

- **Execution** — implementation-heavy work (writing/editing code, boilerplate, refactors) goes to `agy` instead of Claude implementing it directly: `agy --print "<prompt>" --model gemini-3.7-flash-high --add-dir "<smallest folder needed>" --dangerously-skip-permissions`. This burns Gemini's quota, not Claude's.
- **Git stays with Claude.** `agy` never runs `git commit` or `git push` itself, even under `--dangerously-skip-permissions` — that flag covers file edits only. Claude reviews what `agy` produced, then commits/pushes after the user confirms. (This rule exists because on 2026-08-17 `agy`, left fully unsupervised, auto-committed and pushed ~500 unrelated lines to `origin/main` on its own initiative — see [[Jurnal]].)
- **Fallback to normal mode** — when `agy`/Gemini fails, times out, produces wrong or incomplete output, or the task is architecturally sensitive / beyond a fast-cheap model (multi-file reasoning, security-relevant code, anything the recovery-first gate would escalate): stop delegating, say so plainly, and have Claude implement it directly instead. One retry with reduced scope is fine before falling back; don't loop.
- Claude's role either way: plan, write the prompt (or the code), review the result, report back — never silently redo what `agy` already did correctly.
- Use `-c`/`--continue` or `--conversation <id>` to keep one `agy` session across related sub-tasks instead of restarting each call.

---

## Auto-Setup Instructions for New Machine
To automatically install or update all dependencies and skills on any device:
- **Windows (PowerShell)**: `.\setup-skills.ps1`
- **macOS / Linux**: `chmod +x ./setup-skills.sh && ./setup-skills.sh`
