#!/usr/bin/env python3
"""Argus repo health check. Stdlib only, no dependencies.

Run after every task:  python check.py
Exit 0 = pass, exit 1 = fail. Paste the output into the work journal.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
VAULT = ROOT / "CodeVault"
SKIP = {"AGENTS.md", "CLAUDE.md"}          # config copies, not notes
DIACRITICS = "ăâîșțĂÂÎȘȚ"
REQUIRED = [
    "README.md",
    ".gitignore",
    "check.py",
    "CodeVault/Index.md",
    "CodeVault/projects/argus/Plan de implementare.md",
    "CodeVault/projects/argus/Task-uri de start.md",
    "CodeVault/projects/argus/Jurnal.md",
]

failures = []


def notes():
    return [p for p in VAULT.rglob("*.md")
            if ".obsidian" not in p.parts and p.name not in SKIP]


def check_required_files():
    for rel in REQUIRED:
        if not (ROOT / rel).exists():
            failures.append(f"lipseste fisierul obligatoriu: {rel}")


def check_wikilinks():
    """Every [[link]] must point to a note that exists. Inline code is ignored."""
    titles = {p.stem for p in notes()}
    for p in notes():
        body = re.sub(r"`[^`]*`", "", p.read_text(encoding="utf-8"))
        for m in re.finditer(r"\[\[([^\]|#]+)", body):
            target = m.group(1).strip()
            if target not in titles:
                failures.append(f"{p.name}: legatura rupta [[{target}]]")


def check_frontmatter():
    for p in notes():
        head = p.read_text(encoding="utf-8")[:400]
        if not head.startswith("---"):
            failures.append(f"{p.name}: fara frontmatter")
            continue
        for key in ("tags:", "created:", "type:"):
            if key not in head:
                failures.append(f"{p.name}: frontmatter fara {key}")


def check_filenames():
    """Diacritics in filenames break between Windows and Linux. Keep them in the body."""
    for p in VAULT.rglob("*.md"):
        if any(c in p.name for c in DIACRITICS):
            failures.append(f"{p.name}: diacritice in numele fisierului")


def check_no_heavy_files():
    """Imagery must never enter git history — it cannot be removed cheaply later."""
    out = subprocess.run(["git", "ls-files"], cwd=ROOT,
                         capture_output=True, text=True).stdout
    for line in out.splitlines():
        if line.startswith("data/") or line.lower().endswith((".tif", ".tiff", ".las", ".laz")):
            failures.append(f"fisier greu urmarit de git: {line}")


def check_tests():
    """Runs pytest only once tests exist. Silent before that."""
    if not list(ROOT.glob("app/**/test_*.py")):
        return None
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "app"],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        failures.append("pytest a picat:\n" + r.stdout[-2000:])
    return "pytest"


CHECKS = [check_required_files, check_wikilinks, check_frontmatter,
          check_filenames, check_no_heavy_files, check_tests]


def main():
    for fn in CHECKS:
        before = len(failures)
        skipped = fn() is None and fn is check_tests
        status = "SKIP" if skipped else ("FAIL" if len(failures) > before else "OK  ")
        print(f"[{status}] {fn.__name__}")

    print("-" * 50)
    if failures:
        for f in failures:
            print("  ! " + f)
        print(f"\nFAIL: {len(failures)} probleme. NU marca taskul ca terminat.")
        return 1
    print(f"PASS: {len(notes())} note, toate verificarile trecute.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
