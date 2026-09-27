"""Shared models and TOML I/O for the coverage bootstrap tooling.

Only the Python standard library is used (tomllib for parsing, hand-rolled
emitter for writing) so the bootstrap has zero external dependencies.

These three ground-truth sets are the heart of the "no-omission" model:
  * spec_atoms  (A)  -- mechanically parsed from doc/go_spec.html
  * impl_atoms  (B)  -- mechanically scanned from the Go source tree
  * test_atoms  (C)  -- mechanically enumerated from the official test tree

A feature is `verified` only when it has at least one atom in each of A, B, C
AND a passing Rust test. The validator (validate_features.py) enforces the
static half of the four gates on the human-attributed features.toml.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# Repository layout ----------------------------------------------------------
# rust_go_compiler/tools/models.py  -> parents[2] == repo root (learn_compiler/)
REPO_ROOT = Path(__file__).resolve().parents[2]
GO_SOURCE = REPO_ROOT / "go_source_code"
COVERAGE_DIR = REPO_ROOT / "rust_go_compiler" / "coverage"


# Atom records --------------------------------------------------------------
@dataclass
class SpecAtom:
    atom_id: str          # "spec:Source_code_representation"
    kind: str             # "h2" | "h3"
    title: str
    anchor: str           # html id attribute
    source_path: str      # relative to repo root
    line: int


@dataclass
class ImplAtom:
    atom_id: str          # "pragma:build" | "flag:LowerP" | "rules:AMD64.rules" | "obj:x86:asm6.go"
    kind: str             # "pragma" | "flag" | "rules" | "obj"
    name: str             # per-kind: pragma text / flag field / rules filename / obj filename
    source_path: str
    line: int = 0
    extra: dict[str, Any] = field(default_factory=dict)  # e.g. pass, rule_count, arch, help


@dataclass
class TestAtom:
    test_id: str          # "L1:fixedbugs:bug1.go"
    layer: str            # "L1" | "L2" | "L3" | "L4" | "L5" | "adjacent"
    source_path: str
    line: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


# TOML emission -------------------------------------------------------------
def emit_toml(path: Path, header: str, section: str, records: list[dict]) -> None:
    """Write a list of flat string/int dicts as a [[section]] TOML file.

    Hand-rolled on purpose: avoids any external writer dependency. Values
    must be str/int/bool; nested dicts are not supported by this emitter.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if header:
        lines.append(header.rstrip("\n"))
        lines.append("")
    if not records:
        lines.append(f"# (no {section} found)")
    for rec in records:
        lines.append(f"[[{section}]]")
        for key, val in rec.items():
            lines.append(f"{key} = {_toml_value(val)}")
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _toml_value(val: Any) -> str:
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, int):
        return str(val)
    if isinstance(val, str):
        escaped = val.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(val, list):
        return "[" + ", ".join(_toml_value(v) for v in val) + "]"
    raise TypeError(f"unsupported TOML value type: {type(val).__name__}")


def load_toml(path: Path) -> dict[str, Any]:
    """Parse a TOML file (stdlib tomllib, Python >= 3.11)."""
    with open(path, "rb") as f:
        return tomllib.load(f)


def rel(path: Path) -> str:
    """Path relative to repo root, for stable cross-platform anchors."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def load_atom_ids(coverage_dir: Path | None = None) -> tuple[set[str], set[str], set[str]]:
    """Return (spec_ids, impl_ids, test_ids) from the three generated TOML files.

    Consumers use this to check that an attributed features.toml only cites
    atoms that actually exist -- the cross-file reference-integrity check
    that validate_features.py cannot do on its own.
    """
    base = coverage_dir or COVERAGE_DIR
    spec = {r["atom_id"] for r in load_toml(base / "spec_atoms.toml").get("spec_atoms", [])
            if r.get("atom_id")}
    impl = {r["atom_id"] for r in load_toml(base / "impl_atoms.toml").get("impl_atoms", [])
            if r.get("atom_id")}
    tests = {r["test_id"] for r in load_toml(base / "official-tests.toml").get("test_atoms", [])
             if r.get("test_id")}
    return spec, impl, tests
