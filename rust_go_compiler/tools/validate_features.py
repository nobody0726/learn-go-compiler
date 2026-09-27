#!/usr/bin/env python3
"""Four-gates validator for the human-attributed features.toml.

The three extractors produce ground-truth atom sets A/B/C mechanically.
Humans then write coverage/features.toml that ties atoms to feature_ids
and milestone tasks. THIS validator enforces the *static* half of the four
gates on that attributed layer -- it is what makes omissions fail loudly
instead of slipping through a green build.

Gates (static portion enforced here):
  2. triangulation  -- every feature has >=1 spec_atom AND >=1 impl_atom
                       AND >=1 test_atom (no A-only / B-only / C-only)
  3. mutation       -- a `verified` feature must cite a mutation_case_id
                       (evidence that a mutation diff was run for its harness)
  4. negative       -- every feature has >=1 negative_test_id
plus structural: unique feature_id, main_task, target_dim, valid status.

Gate 1 (mechanical generation) is enforced by re-running the extractors and
diffing their output, not by this file.

Usage:
    python tools/validate_features.py coverage/features.toml
Exit code: 0 if valid, 1 if any gate violation.
"""

from __future__ import annotations

import sys
from pathlib import Path

from models import load_toml

ALLOWED_STATUS = {"planned", "partial", "verified"}

# Error codes -- stable, asserted by tests.
E_DUP_ID = "E_DUP_ID"
E_NO_SPEC = "E_NO_SPEC"        # gate 2: triangulation, A side missing
E_NO_IMPL = "E_NO_IMPL"        # gate 2: B side missing
E_NO_TEST = "E_NO_TEST"        # gate 2: C side missing
E_NO_MAIN = "E_NO_MAIN"        # structural
E_NO_NEG = "E_NO_NEG"          # gate 4: negative differential
E_NO_TARGET = "E_NO_TARGET"
E_NO_MUTATION = "E_NO_MUTATION"  # gate 3: mutation evidence for verified
E_BAD_STATUS = "E_BAD_STATUS"


def validate(features: list[dict]) -> list[tuple[str, str, str]]:
    """Return a list of (feature_id, code, message) violations. Empty == valid."""
    errors: list[tuple[str, str, str]] = []
    seen_ids: set[str] = set()

    for feat in features:
        fid = feat.get("feature_id", "<missing>")
        if fid in seen_ids:
            errors.append((fid, E_DUP_ID, "duplicate feature_id"))
        seen_ids.add(fid)

        spec = feat.get("spec_atoms", []) or []
        impl = feat.get("impl_atoms", []) or []
        tests = feat.get("test_ids", []) or []
        neg = feat.get("negative_test_ids", []) or []
        main_task = feat.get("main_task", "")
        target = feat.get("target_dim", "")
        status = feat.get("status", "")
        mutation = feat.get("mutation_case_id", "")

        if not spec:
            errors.append((fid, E_NO_SPEC, "no spec_atoms (gate 2: A side)"))
        if not impl:
            errors.append((fid, E_NO_IMPL, "no impl_atoms (gate 2: B side)"))
        if not tests:
            errors.append((fid, E_NO_TEST, "no test_ids (gate 2: C side)"))
        if not main_task:
            errors.append((fid, E_NO_MAIN, "no main_task"))
        if not neg:
            errors.append((fid, E_NO_NEG, "no negative_test_ids (gate 4)"))
        if not target:
            errors.append((fid, E_NO_TARGET, "no target_dim"))
        if status not in ALLOWED_STATUS:
            errors.append((fid, E_BAD_STATUS, f"status {status!r} not in {ALLOWED_STATUS}"))
        if status == "verified" and not mutation:
            errors.append((fid, E_NO_MUTATION, "verified but no mutation_case_id (gate 3)"))

    return errors


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: validate_features.py <features.toml>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    data = load_toml(path)
    features = data.get("features", [])
    errors = validate(features)
    if not errors:
        print(f"OK: {len(features)} features, 0 violations")
        return 0
    for fid, code, msg in errors:
        print(f"FAIL {code}  {fid}: {msg}")
    print(f"\n{len(errors)} violation(s) across {len(features)} feature(s)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
