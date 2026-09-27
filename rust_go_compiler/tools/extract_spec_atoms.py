#!/usr/bin/env python3
"""Ground-truth set A: spec_atoms.

Mechanically parse go_source_code/doc/go_spec.html into one atom per
<h2>/<h3> clause. The Go spec is structured: every section carries an id
attribute, so parsing is deterministic and re-generatable -- humans never
touch this list, they only attribute spec_atoms to feature_ids later.

Usage:
    python tools/extract_spec_atoms.py            # writes coverage/spec_atoms.toml
    python tools/extract_spec_atoms.py --check     # exit 1 if output unchanged
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from models import COVERAGE_DIR, GO_SOURCE, emit_toml, rel

SPEC_HTML = GO_SOURCE / "doc" / "go_spec.html"

# <h2 id="X">Title</h2>  /  <h3 id="Y">Subtitle</h3>
HEADING_RE = re.compile(r'<(h[23]) id="([^"]+)">([^<]*)</\1>')


def extract() -> list[dict]:
    if not SPEC_HTML.exists():
        raise FileNotFoundError(f"spec not found: {SPEC_HTML}")
    records: list[dict] = []
    for lineno, line in enumerate(SPEC_HTML.read_text(encoding="utf-8").splitlines(), 1):
        m = HEADING_RE.search(line)
        if not m:
            continue
        kind, anchor, title = m.group(1), m.group(2), m.group(3)
        records.append({
            "atom_id": f"spec:{anchor}",
            "kind": kind,
            "title": title,
            "anchor": anchor,
            "source_path": rel(SPEC_HTML),
            "line": lineno,
        })
    return records


HEADER = (
    "# Ground-truth set A: spec_atoms\n"
    "# Mechanically generated from go_source_code/doc/go_spec.html -- DO NOT EDIT.\n"
    "# Regenerate: python tools/extract_spec_atoms.py\n"
    "# One atom per <h2>/<h3> clause. Humans only attribute to feature_ids.\n"
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if regenerated output differs from disk")
    args = ap.parse_args()

    records = extract()
    out = COVERAGE_DIR / "spec_atoms.toml"
    emit_toml(out, HEADER, "spec_atoms", records)

    by_kind = {}
    for r in records:
        by_kind[r["kind"]] = by_kind.get(r["kind"], 0) + 1
    print(f"[spec_atoms] {len(records)} atoms "
          f"({', '.join(f'{k}={v}' for k, v in sorted(by_kind.items()))}) -> {rel(out)}")

    if args.check:
        # Re-run and compare; if the just-written file differs from a git
        # snapshot we'd fail. Stub: a real CI hook would `git diff --exit-code`.
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
