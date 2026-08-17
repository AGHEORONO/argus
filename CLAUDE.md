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

For implementation-heavy work in this workspace (writing/editing code, boilerplate, refactors), delegate execution to the `agy` CLI (Antigravity, Gemini-backed) instead of doing it directly — this moves the token cost off Claude's budget onto Gemini's.

- Command shape: `agy --print "<prompt>" --model gemini-3.7-flash-high --add-dir "<smallest folder needed>" --dangerously-skip-permissions`
- Default model: `gemini-3.7-flash-high`.
- Runs with `--dangerously-skip-permissions` (auto-approves all of agy's own tool actions) — by user choice. Always scope `--add-dir` to the smallest folder the task needs (e.g. a subfolder of `Practica`, never the whole drive).
- Claude's role: plan the task, write the prompt, hand off to `agy`, then read its output/diff and report back. Don't re-implement what `agy` already did.
- Use `-c`/`--continue` or `--conversation <id>` to keep one agy session across related sub-tasks instead of starting fresh each call.
- Still escalate to the user instead of delegating for anything touching secrets, credentials, or destructive git operations — same recovery-first rule as above applies to agy-delegated work too.

---

## Auto-Setup Instructions for New Machine
To automatically install or update all dependencies and skills on any device:
- **Windows (PowerShell)**: `.\setup-skills.ps1`
- **macOS / Linux**: `chmod +x ./setup-skills.sh && ./setup-skills.sh`
