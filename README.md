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

## Aplicație Windows de sine stătătoare

```powershell
.uild-desktop.ps1
```

Produce `dist-desktop\Argus Custode\` (folder cu `.exe`) și `Argus-Custode-windows.zip` (~300 MB).
Backendul pornește pe un port local ales la rulare și servește și interfața din aceeași
origine; fereastra e WebView2 (Edge), preinstalat pe Windows 11.

Datele stau în `%LOCALAPPDATA%\Argus`, împreună cu `argus-desktop.log` — primul lucru de
citit dacă aplicația nu pornește. `ARGUS_DATA_DIR` mută rădăcina în altă parte.

Executabilul e nesemnat: prima rulare arată un avertisment SmartScreen
(*Mai multe informații → Executați oricum*).

Deploy-ul web rămâne neschimbat — aceeași bază de cod, alt mod de build.

## Layout

| Path | What |
|---|---|
| `CodeVault/projects/argus/` | plan, decisions, work log, open questions |
| `CodeVault/wiki/` | durable technical notes |
| `CodeVault/raw/` | unprocessed captures |
| `data/` | imagery and rasters — gitignored, never pushed |

## Status

Planning. No code yet, no flight data yet. See `CodeVault/projects/argus/Plan de implementare.md`.
