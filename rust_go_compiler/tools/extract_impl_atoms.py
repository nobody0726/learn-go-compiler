#!/usr/bin/env python3
"""Ground-truth set B: impl_atoms.

Mechanically scan the Go source tree for implementation-only contracts that
the spec does NOT mention but the compiler must implement: //go: pragmas,
cmd/compile flags, SSA rewrite rules (per pass), and per-arch obj files.

This is the set that closes the "B only = implementation-only contract"
danger zone (PGO / write barrier / ABIInternal / PCLN / escape diagnostics
have no spec clause -- only this scan finds them).

Usage:
    python tools/extract_impl_atoms.py
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

from models import COVERAGE_DIR, GO_SOURCE, emit_toml, rel

COMPILE_INTERNAL = GO_SOURCE / "src" / "cmd" / "compile" / "internal"
SSA_GEN = COMPILE_INTERNAL / "ssa" / "_gen"
OBJ_DIR = GO_SOURCE / "src" / "cmd" / "internal" / "obj"
FLAG_GO = COMPILE_INTERNAL / "base" / "flag.go"

PRAGMA_RE = re.compile(r'//go:([a-zA-Z_]+)')
# CmdFlags struct fields carry a help:"..." tag (the help text is escaped as
# \" inside the tag string). Flag name = the struct field name.
FLAG_FIELD_RE = re.compile(r'^\s*([A-Z][A-Za-z0-9_]*)\s+\S')
HELP_RE = re.compile(r'help:\\?"(.+?)\\?"')
RULE_LINE_RE = re.compile(r'=>')  # a rules line contains =>; comment lines start with //


def _is_real_go(path: Path) -> bool:
    """Exclude _test.go and testdata/ -- those hold pragma/parser fixtures."""
    s = str(path)
    return s.endswith(".go") and not s.endswith("_test.go") and "testdata" not in s


# --- pragmas ---------------------------------------------------------------
def collect_pragmas() -> list[dict]:
    seen: dict[str, dict] = {}
    counts: dict[str, int] = defaultdict(int)
    for path in COMPILE_INTERNAL.rglob("*.go"):
        if not _is_real_go(path):
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for m in PRAGMA_RE.finditer(line):
                name = m.group(1)
                counts[name] += 1
                if name not in seen:
                    seen[name] = {
                        "atom_id": f"pragma:{name}",
                        "kind": "pragma",
                        "name": f"//go:{name}",
                        "source_path": rel(path),
                        "line": lineno,
                        "count": 0,
                    }
                seen[name]["count"] = counts[name]
    return sorted(seen.values(), key=lambda r: r["atom_id"])


# --- flags (CmdFlags struct fields) ----------------------------------------
def collect_flags() -> list[dict]:
    records: list[dict] = []
    if not FLAG_GO.exists():
        return records
    in_struct = False
    for lineno, line in enumerate(FLAG_GO.read_text(encoding="utf-8").splitlines(), 1):
        if "type CmdFlags struct" in line:
            in_struct = True
            continue
        if in_struct:
            if line.startswith("}"):
                break
            m = FLAG_FIELD_RE.match(line)
            if m and '"help:' in line:
                field = m.group(1)
                hm = HELP_RE.search(line)
                help_text = hm.group(1) if hm else ""
                records.append({
                    "atom_id": f"flag:{field}",
                    "kind": "flag",
                    "name": field,
                    "help": help_text,
                    "source_path": rel(FLAG_GO),
                    "line": lineno,
                })
    return records


# --- SSA rewrite rules, grouped by pass ------------------------------------
PASS_OF = {
    "generic": "opt",
    "dec": "decompose-builtin",
    "dec64": "decompose-builtin",
    "divmod": "divmod",
    "divisible": "divisible",
}


def _pass_of_file(stem: str) -> str:
    """Derive the SSA pass that consumes a .rules file from its stem."""
    if stem in PASS_OF:
        return PASS_OF[stem]
    if stem.startswith("simd"):
        return "simd-lower"
    if stem.endswith("latelower"):
        return "latelower"
    if stem.endswith("splitload"):
        return "splitload"  # note: not a pass, called per-value; recorded as its own bucket
    return "lower"  # <ARCH>.rules main lowering


def collect_rules() -> list[dict]:
    records: list[dict] = []
    if not SSA_GEN.exists():
        return records
    for rules_file in sorted(SSA_GEN.glob("*.rules")):
        rule_count = 0
        for line in rules_file.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if not s or s.startswith("//"):
                continue
            if RULE_LINE_RE.search(s):
                rule_count += 1
        records.append({
            "atom_id": f"rules:{rules_file.name}",
            "kind": "rules",
            "name": rules_file.name,
            "pass": _pass_of_file(rules_file.stem),
            "rule_count": rule_count,
            "source_path": rel(rules_file),
            "line": 1,
        })
    return records


# --- per-arch obj backend files --------------------------------------------
def collect_obj_files() -> list[dict]:
    records: list[dict] = []
    if not OBJ_DIR.exists():
        return records
    for arch_dir in sorted(d for d in OBJ_DIR.iterdir() if d.is_dir()):
        arch = arch_dir.name
        for go_file in sorted(arch_dir.glob("*.go")):
            if go_file.name.endswith("_test.go"):
                continue
            n = sum(1 for _ in go_file.read_text(encoding="utf-8", errors="replace").splitlines())
            records.append({
                "atom_id": f"obj:{arch}:{go_file.name}",
                "kind": "obj",
                "name": go_file.name,
                "arch": arch,
                "loc": n,
                "source_path": rel(go_file),
                "line": 1,
            })
    return records


def main() -> int:
    records: list[dict] = []
    for kind, fn in (("pragma", collect_pragmas),
                     ("flag", collect_flags),
                     ("rules", collect_rules),
                     ("obj", collect_obj_files)):
        recs = fn()
        records.extend(recs)
        print(f"[impl_atoms] {kind}: {len(recs)}")
    out = COVERAGE_DIR / "impl_atoms.toml"
    emit_toml(out, _HEADER, "impl_atoms", records)
    print(f"[impl_atoms] total {len(records)} -> {rel(out)}")
    return 0


_HEADER = (
    "# Ground-truth set B: impl_atoms\n"
    "# Mechanically scanned from go_source_code -- DO NOT EDIT.\n"
    "# Regenerate: python tools/extract_impl_atoms.py\n"
    "# Categories: pragma / flag / rules(per pass) / obj(per arch).\n"
)


if __name__ == "__main__":
    sys.exit(main())
