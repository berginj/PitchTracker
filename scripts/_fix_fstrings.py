"""One-off fixer: strip the f prefix from f-strings that have no placeholders.

Uses flake8's F541 report (file:line:col) and removes the single f/F prefix
character at each location. Processes occurrences right-to-left per line so
column offsets stay valid.
"""
import subprocess
import sys
from collections import defaultdict

proc = subprocess.run(
    [sys.executable, "-m", "flake8", ".", "--select=F541"],
    capture_output=True,
    text=True,
)
locs = defaultdict(list)
for line in proc.stdout.splitlines():
    parts = line.split(":", 3)
    if len(parts) < 4:
        continue
    path, lno, col = parts[0], int(parts[1]), int(parts[2])
    locs[path].append((lno, col))

total = 0
for path, items in locs.items():
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.readlines()
    # right-to-left, bottom-up
    for lno, col in sorted(items, key=lambda t: (t[0], t[1]), reverse=True):
        text = lines[lno - 1]
        idx = col - 1
        if idx < len(text) and text[idx] in ("f", "F") and idx + 1 < len(text) and text[idx + 1] in ("'", '"'):
            lines[lno - 1] = text[:idx] + text[idx + 1:]
            total += 1
        else:
            print(f"SKIP {path}:{lno}:{col} char={text[idx:idx+2]!r}")
    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(lines)

print(f"Removed {total} f prefixes")
