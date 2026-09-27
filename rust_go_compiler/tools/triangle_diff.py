#!/usr/bin/env python3
"""Triangle diff: A(spec) x B(impl) x C(test) x features.toml.

`validate_features.py` reads features.toml alone -- it can tell you an entry
is malformed, but never which ground-truth atoms *nobody has claimed*. This
script answers that question. It cross-products the three machine-generated
sets against the human attribution layer and prints the three red zones the
no-omission model is built around:

  A-only  spec clause with no feature_id     -> spec dead corner
  B-only  impl atom with no feature_id       -> impl-only contract
  C-only  official test with no feature_id   -> runtime / unmapped behavior

Section 0 catches *dangling references*: a feature citing an atom_id absent
from the generated sets. Those are data errors, not TODOs -- a dangling
citation claims nothing while looking like it claims something, which
silently inflates the red zones. Exit code 1 when any are found; the red
zones themselves are expected while attribution is in progress and do not
fail the run.

Usage:
    python tools/triangle_diff.py                    # text summary (truncated)
    python tools/triangle_diff.py --full             # no truncation
    python tools/triangle_diff.py --json             # machine-readable, always full
    python tools/triangle_diff.py --out coverage/triangle-diff.txt
Exit: 0 = red zones only, 1 = dangling references found, 2 = usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from models import COVERAGE_DIR, load_toml

# Which features.toml field cites which ground-truth set.
FIELD_TO_SET = {
    "spec_atoms": "spec",
    "impl_atoms": "impl",
    "test_ids": "test",
    "negative_test_ids": "test",   # a counter-example is a real claim on a test
}
SET_KEYS = {"spec": "atom_id", "impl": "atom_id", "test": "test_id"}


@dataclass(frozen=True)
class DanglingRef:
    feature_id: str
    field: str      # spec_atoms | impl_atoms | test_ids | negative_test_ids
    atom_id: str


@dataclass
class DiffReport:
    spec_atoms: list[dict] = field(default_factory=list)
    impl_atoms: list[dict] = field(default_factory=list)
    test_atoms: list[dict] = field(default_factory=list)
    features: list[dict] = field(default_factory=list)
    claimed: dict[str, set[str]] = field(default_factory=lambda: {"spec": set(), "impl": set(), "test": set()})
    dangling: list[DanglingRef] = field(default_factory=list)
    a_only: list[dict] = field(default_factory=list)
    b_only: list[dict] = field(default_factory=list)
    c_only: list[dict] = field(default_factory=list)

    def total(self, which: str) -> int:
        return {"spec": len(self.spec_atoms), "impl": len(self.impl_atoms),
                "test": len(self.test_atoms)}[which]

    def coverage(self, which: str) -> tuple[int, int, float]:
        claimed = len(self.claimed[which])
        total = self.total(which)
        pct = (100.0 * claimed / total) if total else 0.0
        return claimed, total, pct

    @property
    def zones(self) -> dict[str, list[dict]]:
        return {"A-only": self.a_only, "B-only": self.b_only, "C-only": self.c_only}


def _index(records: list[dict], key: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for rec in records:
        k = rec.get(key)
        if k:
            out[k] = rec
    return out


def compute_diff(spec_atoms: list[dict], impl_atoms: list[dict],
                 test_atoms: list[dict], features: list[dict]) -> DiffReport:
    """Pure function: cross-product the four inputs into a DiffReport."""
    stores = {
        "spec": _index(spec_atoms, "atom_id"),
        "impl": _index(impl_atoms, "atom_id"),
        "test": _index(test_atoms, "test_id"),
    }
    report = DiffReport(spec_atoms=list(spec_atoms), impl_atoms=list(impl_atoms),
                        test_atoms=list(test_atoms), features=list(features))

    for feat in features:
        fid = feat.get("feature_id", "<missing>")
        for fld, which in FIELD_TO_SET.items():
            for atom_id in feat.get(fld) or []:
                if atom_id in stores[which]:
                    report.claimed[which].add(atom_id)
                else:
                    report.dangling.append(DanglingRef(fid, fld, atom_id))

    report.a_only = [a for a in spec_atoms if a.get("atom_id") not in report.claimed["spec"]]
    report.b_only = [a for a in impl_atoms if a.get("atom_id") not in report.claimed["impl"]]
    report.c_only = [t for t in test_atoms if t.get("test_id") not in report.claimed["test"]]
    return report


def group_by_kind(atoms: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for a in atoms:
        out.setdefault(a.get("kind", "?"), []).append(a)
    return dict(sorted(out.items()))


def test_group(test_id: str) -> str:
    """Bucket a test_id for aggregation: 'L1:fixedbugs:bug1.go' -> 'L1:fixedbugs'."""
    parts = test_id.split(":")
    if parts[0] == "L5":
        return "L5:script"
    if len(parts) >= 3:
        return f"{parts[0]}:{parts[1]}"
    return parts[0]


def group_tests(atoms: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for a in atoms:
        g = test_group(a.get("test_id", "?"))
        counts[g] = counts.get(g, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def group_by_task(features: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in features:
        t = f.get("main_task") or "<none>"
        counts[t] = counts.get(t, 0) + 1
    return dict(sorted(counts.items()))


# Rendering ------------------------------------------------------------------
def render_text(report: DiffReport, top: int = 10, full: bool = False) -> str:
    def show(n: int) -> int:
        return n if full else min(n, top)

    L: list[str] = []
    bar = "=" * 74
    L.append(bar)
    L.append("triangle diff -- A(spec) x B(impl) x C(test) x features.toml")
    L.append(bar)

    cs, ts_, ps = report.coverage("spec")
    ci, ti, pi = report.coverage("impl")
    ct, tt, pt = report.coverage("test")
    L.append(f"baseline   A={ts_} spec atoms   B={ti} impl atoms   "
             f"C={tt} tests   features={len(report.features)}")
    L.append(f"claimed    A {cs:>5}/{ts_} ({ps:5.1f}%)   "
             f"B {ci:>5}/{ti} ({pi:5.1f}%)   C {ct:>5}/{tt} ({pt:5.1f}%)")
    L.append("")

    L.append(f"[0] dangling references (feature cites an atom that does not exist)   "
             f"{len(report.dangling)}")
    if not report.dangling:
        L.append("    none -- the attribution layer only cites atoms that really exist")
    else:
        for d in report.dangling[:show(len(report.dangling))]:
            L.append(f"    {d.feature_id}  {d.field} -> {d.atom_id}  (NOT IN GROUND TRUTH)")
        if not full and len(report.dangling) > top:
            L.append(f"    ... {len(report.dangling) - top} more")
    L.append("")

    L.append(f"[1] A-only red zone: spec clauses nobody claims            "
             f"{len(report.a_only)}/{ts_}")
    for a in report.a_only[:show(len(report.a_only))]:
        L.append(f"    {a.get('atom_id',''):<40} {a.get('kind',''):<3} line {a.get('line','?')}")
    if not full and len(report.a_only) > top:
        L.append(f"    ... {len(report.a_only) - top} more  (--full to list all)")
    L.append("")

    L.append(f"[2] B-only red zone: impl atoms nobody claims              "
             f"{len(report.b_only)}/{ti}")
    by_kind = group_by_kind(report.b_only)
    summary = "   ".join(f"{k} {len(v)}" for k, v in by_kind.items())
    L.append(f"    by kind: {summary}")
    shown = 0
    for kind, atoms in by_kind.items():
        for a in atoms:
            if shown >= show(len(report.b_only)):
                break
            note = a.get("help") or a.get("pass") or a.get("arch") or ""
            L.append(f"    {a.get('atom_id',''):<34} {kind:<7} {note}")
            shown += 1
    if not full and len(report.b_only) > top:
        L.append(f"    ... {len(report.b_only) - top} more  (--full to list all)")
    L.append("")

    L.append(f"[3] C-only red zone: tests nobody claims                   "
             f"{len(report.c_only)}/{tt}")
    by_layer: dict[str, int] = {}
    for a in report.c_only:
        lay = a.get("layer", "?")
        by_layer[lay] = by_layer.get(lay, 0) + 1
    L.append("    by layer: " + "   ".join(f"{k} {v}" for k, v in sorted(by_layer.items())))
    groups = group_tests(report.c_only)
    L.append(f"    by group (top {show(len(groups))} of {len(groups)}):")
    for g, n in list(groups.items())[:show(len(groups))]:
        L.append(f"      {g:<28} {n:>5} unclaimed")
    if not full and len(groups) > top:
        L.append(f"      ... {len(groups) - top} more groups")
    L.append("")

    L.append("[4] attribution by milestone")
    for task, n in group_by_task(report.features).items():
        L.append(f"    {task:<10} {n} feature(s)")
    L.append("")

    if report.a_only:
        L.append(f"[5] next attribution candidates (spec order, first {show(10)})")
        for a in report.a_only[:show(10)]:
            L.append(f"    {a.get('atom_id','')}")
        L.append("")

    total_red = len(report.a_only) + len(report.b_only) + len(report.c_only)
    L.append(bar)
    L.append(f"red zones total {total_red}   dangling {len(report.dangling)}")
    if report.dangling:
        L.append("VERDICT: FAIL -- fix dangling references first; they inflate the red zones.")
    else:
        L.append("VERDICT: OK -- no data errors. Red zones are unclaimed work, not bugs.")
    L.append(bar)
    return "\n".join(L)


def render_json(report: DiffReport) -> str:
    payload = {
        "baseline": {"spec": report.total("spec"), "impl": report.total("impl"),
                     "test": report.total("test"), "features": len(report.features)},
        "claimed": {w: {"count": len(report.claimed[w]), "of": report.total(w),
                        "percent": round(report.coverage(w)[2], 2)}
                    for w in ("spec", "impl", "test")},
        "dangling": [{"feature_id": d.feature_id, "field": d.field, "atom_id": d.atom_id}
                     for d in report.dangling],
        "zones": {
            "A-only": [{"atom_id": a.get("atom_id"), "kind": a.get("kind"),
                        "title": a.get("title"), "line": a.get("line"),
                        "source_path": a.get("source_path")} for a in report.a_only],
            "B-only": [{"atom_id": a.get("atom_id"), "kind": a.get("kind"),
                        "name": a.get("name"), "source_path": a.get("source_path")}
                       for a in report.b_only],
            "C-only": [{"test_id": t.get("test_id"), "layer": t.get("layer"),
                        "source_path": t.get("source_path")} for t in report.c_only],
        },
        "zones_grouped": {
            "B-only_by_kind": {k: len(v) for k, v in group_by_kind(report.b_only).items()},
            "C-only_by_group": group_tests(report.c_only),
        },
        "by_milestone": group_by_task(report.features),
        "red_total": len(report.a_only) + len(report.b_only) + len(report.c_only),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


# CLI ------------------------------------------------------------------------
def load_inputs(coverage_dir: Path, features_path: Path | None) -> DiffReport:
    features_path = features_path or (coverage_dir / "features.toml")
    spec = load_toml(coverage_dir / "spec_atoms.toml").get("spec_atoms", [])
    impl = load_toml(coverage_dir / "impl_atoms.toml").get("impl_atoms", [])
    tests = load_toml(coverage_dir / "official-tests.toml").get("test_atoms", [])
    feats = load_toml(features_path).get("features", [])
    return compute_diff(spec, impl, tests, feats)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="triangle diff over the coverage sets")
    ap.add_argument("--coverage-dir", type=Path, default=COVERAGE_DIR)
    ap.add_argument("--features", type=Path, default=None,
                    help="default: <coverage-dir>/features.toml")
    ap.add_argument("--json", action="store_true", help="emit JSON (always full)")
    ap.add_argument("--full", action="store_true", help="do not truncate text lists")
    ap.add_argument("--top", type=int, default=10, help="items per section (default 10)")
    ap.add_argument("--out", type=Path, default=None, help="also write the report here")
    args = ap.parse_args(argv)

    report = load_inputs(args.coverage_dir, args.features)
    content = render_json(report) if args.json else render_text(report, args.top, args.full)
    print(content)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(content + "\n", encoding="utf-8")
        print(f"\n[triangle_diff] report written to {args.out}", file=sys.stderr)
    return 1 if report.dangling else 0


if __name__ == "__main__":
    sys.exit(main())
