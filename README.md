# Argus Custode

Change detection over drone orthophotos: fly the same area twice, get the differences flagged on a map.

Short name: **Argus**. Planning and notes live in `CodeVault/` (Obsidian vault, written in Romanian). Code, commits and filenames are English.

## Continue on another machine

```bash
git clone https://github.com/AGHEORONO/argus.git
cd argus
```

Windows: `.\setup-skills.ps1` — macOS/Linux: `chmod +x setup-skills.sh && ./setup-skills.sh`

Then open `CodeVault/` as a vault in Obsidian and start from `projects/argus/Argus Custode.md`.

### Obsidian Git (auto-sync for notes)

Settings → Community plugins → Browse → search "Obsidian Git" → Install → Enable.
Defaults are fine: it auto-commits on a timer and pulls when the vault opens. Install it on every machine. Code changes still go through the CLI.

## Layout

| Path | What |
|---|---|
| `CodeVault/projects/argus/` | plan, decisions, work log, open questions |
| `CodeVault/wiki/` | durable technical notes |
| `CodeVault/raw/` | unprocessed captures |
| `data/` | imagery and rasters — gitignored, never pushed |

## Status

Planning. No code yet, no flight data yet. See `CodeVault/projects/argus/Plan de implementare.md`.
