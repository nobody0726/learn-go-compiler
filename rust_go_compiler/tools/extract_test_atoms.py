#!/usr/bin/env python3
"""Ground-truth set C: test_atoms (official test inventory).

Mechanically enumerate the official test tree, mirroring the runner's own
discovery rules:

  L1  test/<dir>/*.go   -- direct .go in each dir listed by testdir dirs[]
                           (goFiles is non-recursive: os.ReadDir, top level)
  L2  test/codegen      -- NOT a separate atom; the asmcheck assertion count is
                           attached to the L1 atom (also_in = ["L2"]). dirs[]
                           already contains "codegen", so emitting a second
                           atom for the same file double-counted all 87 of them.
  L5  cmd/compile/testdata/script/*.txt

L3/L4 (cmd/compile/internal/test, *_test.go) and the adjacent-toolchain
inventory (obj/goobj/asm/link/pkgbits) are scaffolded as counts only here;
their per-id enumeration lands with B0.2 full implementation.

Usage:
    python tools/extract_test_atoms.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from models import COVERAGE_DIR, GO_SOURCE, emit_toml, rel

TEST_ROOT = GO_SOURCE / "test"
TESTDIR_GO = GO_SOURCE / "src" / "cmd" / "internal" / "testdir" / "testdir_test.go"
SCRIPT_DIR = GO_SOURCE / "src" / "cmd" / "compile" / "testdata" / "script"

DIRS_RE = re.compile(r'dirs\s*=\s*\[\]string\{([^}]*)\}')
ASMCHECK_RE = re.compile(r'^\s*//\s*[a-z0-9]+:')  # // amd64:"..." style


def _dirs() -> list[str]:
    """Read the dirs slice from testdir_test.go (the runner's own list)."""
    if not TESTDIR_GO.exists():
        return []
    m = DIRS_RE.search(TESTDIR_GO.read_text(encoding="utf-8"))
    if not m:
        return []
    raw = m.group(1)
    return [s.strip().strip('"') for s in raw.split(",") if s.strip().strip('"')]


def _list_go(dir_path: Path) -> list[str]:
    if not dir_path.is_dir():
        return []
    return sorted(f.name for f in dir_path.iterdir()
                  if f.name.endswith(".go") and not f.name.startswith("."))


def _asmcheck_count(path: Path) -> int:
    """Number of // arch:"..." assertion lines in a codegen test file."""
    n = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if ASMCHECK_RE.match(line):
            n += 1
    return n


def collect_l1() -> list[dict]:
    """L1: every .go directly under a dir listed by the runner's dirs[].

    One physical file is one atom. codegen/ additionally carries the L2
    (asmcheck) view; that is recorded as an attribute on the same atom rather
    than as a second atom, because the same file must not need two feature_ids.
    """
    records: list[dict] = []
    for d in _dirs():
        dpath = TEST_ROOT / d
        for name in _list_go(dpath):
            rec: dict = {
                "test_id": f"L1:{d}:{name}",
                "layer": "L1",
                "source_path": rel(dpath / name),
                "line": 1,
            }
            if d == "codegen":
                rec["also_in"] = ["L2"]
                rec["asmcheck_assertions"] = _asmcheck_count(dpath / name)
            records.append(rec)
    return records


def collect_l5() -> list[dict]:
    records: list[dict] = []
    if not SCRIPT_DIR.is_dir():
        return records
    for txt in sorted(SCRIPT_DIR.glob("*.txt")):
        records.append({
            "test_id": f"L5:{txt.name}",
            "layer": "L5",
            "source_path": rel(txt),
            "line": 1,
        })
    return records


def collect_l3_l4_counts() -> list[dict]:
    """Scaffolding: per-layer file counts only, per-id enumeration is B0.2."""
    out: list[dict] = []
    l3 = GO_SOURCE / "src" / "cmd" / "compile" / "internal" / "test"
    if l3.is_dir():
        n = len([p for p in l3.rglob("*.go") if not p.name.endswith("_test.go")])
        out.append({"test_id": "L3:internal/test", "layer": "L3",
                    "file_count": n, "source_path": rel(l3), "line": 1})
    return out


def main() -> int:
    records: list[dict] = []
    for fn, label in ((collect_l1, "L1 (+L2 attrs)"),
                      (collect_l3_l4_counts, "L3/L4-counts"), (collect_l5, "L5")):
        recs = fn()
        records.extend(recs)
        print(f"[test_atoms] {label}: {len(recs)}")
    out = COVERAGE_DIR / "official-tests.toml"
    emit_toml(out, _HEADER, "test_atoms", records)
    print(f"[test_atoms] total {len(records)} -> {rel(out)}")
    return 0


_HEADER = (
    "# Ground-truth set C: test_atoms\n"
    "# Mechanically enumerated from go_source_code/test and compile/testdata -- DO NOT EDIT.\n"
    "# Regenerate: python tools/extract_test_atoms.py\n"
    "# Layers: L1(test dir .go) / L3(internal/test) / L5(script .txt)\n"
    "# codegen .go carry also_in=[\"L2\"] + asmcheck_assertions rather than a 2nd atom.\n"
)


if __name__ == "__main__":
    sys.exit(main())
