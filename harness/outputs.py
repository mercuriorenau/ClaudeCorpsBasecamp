"""Writers: CSV formatting rules, latest/ copy, history append, metadata, SCHEMA.md."""

import csv
import json
import shutil
from pathlib import Path

from . import schema


def fmt(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        s = f"{value:.6f}".rstrip("0").rstrip(".")
        return "0" if s in ("", "-0") else s
    return str(value)


def write_csv(path, columns, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(columns)
        for r in rows:
            w.writerow([fmt(r.get(c)) for c in columns])


def append_history(path, rows):
    cols = [c for c, _ in schema.HISTORY_COLUMNS]
    path = Path(path)
    new = not path.exists() or path.stat().st_size == 0
    if not new:
        with open(path, encoding="utf-8-sig", newline="") as f:
            existing = next(csv.reader(f), [])
        if existing != cols:
            raise ValueError(
                f"{path} has a different header than this harness writes; refusing to append. "
                f"Rename the old file to keep it and re-run.")
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        if new:
            w.writerow(cols)
        for r in rows:
            w.writerow([fmt(r.get(c)) for c in cols])


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, sort_keys=False)
        f.write("\n")


def refresh_latest(run_dir, latest_dir):
    latest_dir = Path(latest_dir)
    latest_dir.mkdir(parents=True, exist_ok=True)
    for old in latest_dir.iterdir():
        if old.is_file():
            old.unlink()
    for f in Path(run_dir).iterdir():
        if f.is_file():
            shutil.copy2(f, latest_dir / f.name)


def write_schema(results_dir):
    with open(Path(results_dir) / "SCHEMA.md", "w", encoding="utf-8") as f:
        f.write(schema.render_schema_md())
