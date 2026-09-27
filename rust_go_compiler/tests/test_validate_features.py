#!/usr/bin/env python3
"""RED-first unit tests for the four-gates validator.

Each case builds a feature dict in memory and asserts that validate() either
accepts it (GREEN) or rejects it with a specific gate error (RED). If
validate() were a no-op stub, every RED case here would fail -- which is the
TDD contract: the test proves the gate exists.

Run:  python -m unittest tests.test_validate_features -v
     (stdlib only; no pytest dependency.)
"""

from __future__ import annotations

import unittest
import sys
from pathlib import Path

# Make `tools` importable when running from rust_go_compiler/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import validate_features as V  # noqa: E402


def _valid(**overrides) -> dict:
    """A feature that passes all gates; tests perturb one field to break it."""
    base = {
        "feature_id": "f",
        "spec_atoms": ["spec:Short_var_declarations"],
        "impl_atoms": ["impl:types2/assignments.go:shortVarDecl"],
        "test_ids": ["L3:shortvar1.go"],
        "negative_test_ids": ["L1:assign2.go"],
        "main_task": "M1.1",
        "target_dim": "generic",
        "status": "partial",
    }
    base.update(overrides)
    return base


def _codes(errs) -> set:
    return {code for _fid, code, _msg in errs}


class ValidateGatesTest(unittest.TestCase):

    # --- GREEN: valid inventories are accepted ----------------------------
    def test_partial_valid(self):
        self.assertEqual([], V.validate([_valid()]))

    def test_verified_with_mutation_valid(self):
        f = _valid(status="verified", mutation_case_id="mut:flip-loop-var")
        self.assertEqual([], V.validate([f]))

    # --- Gate 2: triangulation (A/B/C sides) ------------------------------
    def test_red_no_spec_atoms(self):
        errs = V.validate([_valid(spec_atoms=[])])
        self.assertIn(V.E_NO_SPEC, _codes(errs))

    def test_red_no_impl_atoms(self):
        errs = V.validate([_valid(impl_atoms=[])])
        self.assertIn(V.E_NO_IMPL, _codes(errs))

    def test_red_no_test_ids(self):
        errs = V.validate([_valid(test_ids=[])])
        self.assertIn(V.E_NO_TEST, _codes(errs))

    # --- Gate 4: negative differential ------------------------------------
    def test_red_no_negative(self):
        errs = V.validate([_valid(negative_test_ids=[])])
        self.assertIn(V.E_NO_NEG, _codes(errs))

    # --- Gate 3: mutation evidence for verified --------------------------
    def test_red_verified_without_mutation(self):
        errs = V.validate([_valid(status="verified", mutation_case_id="")])
        self.assertIn(V.E_NO_MUTATION, _codes(errs))

    # --- Structural ------------------------------------------------------
    def test_red_duplicate_id(self):
        errs = V.validate([_valid(feature_id="dup"), _valid(feature_id="dup")])
        self.assertIn(V.E_DUP_ID, _codes(errs))

    def test_red_no_main_task(self):
        errs = V.validate([_valid(main_task="")])
        self.assertIn(V.E_NO_MAIN, _codes(errs))

    def test_red_no_target_dim(self):
        errs = V.validate([_valid(target_dim="")])
        self.assertIn(V.E_NO_TARGET, _codes(errs))

    def test_red_bad_status(self):
        errs = V.validate([_valid(status="done")])
        self.assertIn(V.E_BAD_STATUS, _codes(errs))

    # --- A broken inventory must not silently pass -----------------------
    def test_red_any_single_break_is_caught(self):
        """Each gate violation, alone, must produce at least one error."""
        for field, val, expected in [
            ("spec_atoms", [], V.E_NO_SPEC),
            ("impl_atoms", [], V.E_NO_IMPL),
            ("test_ids", [], V.E_NO_TEST),
            ("negative_test_ids", [], V.E_NO_NEG),
            ("main_task", "", V.E_NO_MAIN),
            ("target_dim", "", V.E_NO_TARGET),
        ]:
            with self.subTest(field=field):
                self.assertIn(expected, _codes(V.validate([_valid(**{field: val})])))


if __name__ == "__main__":
    unittest.main(verbosity=2)
