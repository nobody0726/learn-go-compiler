#!/usr/bin/env python3
"""RED-first unit tests for tools/triangle_diff.py.

Run:
    PYTHONPATH=tools python -m unittest tests.test_triangle_diff -v

Every test here is written against the *contract* of the triangle diff:
the three red zones plus the dangling-reference check. Fixtures are small
hand-written dicts so the assertions are about logic, not about the current
size of the Go tree.
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from triangle_diff import (
    main,
    compute_diff,
    group_by_kind,
    test_group,
    render_text,
    render_json,
)


def spec(atom_id: str) -> dict:
    return {"atom_id": atom_id, "kind": "h2", "title": atom_id, "line": 1,
            "source_path": "go_source_code/doc/go_spec.html"}


def impl(atom_id: str, kind: str = "flag") -> dict:
    return {"atom_id": atom_id, "kind": kind, "name": atom_id.split(":")[-1],
            "source_path": "go_source_code/x.go", "line": 1}


def test(test_id: str, layer: str = "L1") -> dict:
    return {"test_id": test_id, "layer": layer, "source_path": "go_source_code/test/x.go", "line": 1}


def feature(fid: str, spec_atoms=(), impl_atoms=(), test_ids=(),
            negative=(), task: str = "M0.1") -> dict:
    return {"feature_id": fid, "spec_atoms": list(spec_atoms), "impl_atoms": list(impl_atoms),
            "test_ids": list(test_ids), "negative_test_ids": list(negative), "main_task": task}


class TestRedZones(unittest.TestCase):
    def test_fully_claimed_has_no_red_zones(self):
        rep = compute_diff(
            [spec("spec:A")], [impl("flag:A")], [test("L1:.:a.go")],
            [feature("a", ["spec:A"], ["flag:A"], ["L1:.:a.go"], ["L1:.:a.go"])],
        )
        self.assertEqual([], rep.a_only)
        self.assertEqual([], rep.b_only)
        self.assertEqual([], rep.c_only)
        self.assertEqual([], rep.dangling)

    def test_a_only_detected(self):
        rep = compute_diff([spec("spec:A"), spec("spec:B")], [], [],
                           [feature("a", ["spec:A"], ["flag:Z"], ["L1:.:a.go"])])
        self.assertEqual(["spec:B"], [a["atom_id"] for a in rep.a_only])

    def test_b_only_detected(self):
        rep = compute_diff([], [impl("flag:A"), impl("rules:AMD64.rules", "rules")], [],
                           [feature("a", ["spec:S"], ["flag:A"], ["L1:.:a.go"])])
        self.assertEqual(["rules:AMD64.rules"], [a["atom_id"] for a in rep.b_only])

    def test_c_only_detected(self):
        rep = compute_diff([], [], [test("L1:.:a.go"), test("L2:codegen:b.go", "L2")],
                           [feature("a", ["spec:S"], ["flag:F"], ["L1:.:a.go"])])
        self.assertEqual(["L2:codegen:b.go"], [t["test_id"] for t in rep.c_only])

    def test_empty_features_means_everything_is_red(self):
        rep = compute_diff([spec("spec:A")], [impl("flag:F")], [test("L1:.:a.go")], [])
        self.assertEqual(1, len(rep.a_only))
        self.assertEqual(1, len(rep.b_only))
        self.assertEqual(1, len(rep.c_only))

    def test_atom_shared_by_two_features_is_claimed(self):
        rep = compute_diff([], [], [test("L1:.:a.go")],
                           [feature("f1", ["spec:A"], ["flag:F"], ["L1:.:a.go"]),
                            feature("f2", ["spec:A"], ["flag:F"])])
        self.assertEqual([], rep.c_only)
        self.assertEqual([], rep.a_only)

    def test_negative_test_ids_count_as_a_claim(self):
        """A counter-example test is a real claim; it must not show up as C-only."""
        rep = compute_diff([], [], [test("L1:.:neg.go")],
                           [feature("f", ["spec:A"], ["flag:F"], ["L1:.:pos.go"],
                                    negative=["L1:.:neg.go"])])
        self.assertEqual([], rep.c_only)


class TestDanglingReferences(unittest.TestCase):
    def test_dangling_spec_reference_reported(self):
        rep = compute_diff([spec("spec:A")], [impl("flag:F")], [test("L1:.:a.go")],
                           [feature("f", ["spec:NOT_THERE"], ["flag:F"], ["L1:.:a.go"])])
        self.assertEqual(1, len(rep.dangling))
        d = rep.dangling[0]
        self.assertEqual("f", d.feature_id)
        self.assertEqual("spec_atoms", d.field)
        self.assertEqual("spec:NOT_THERE", d.atom_id)

    def test_dangling_test_reference_reported(self):
        rep = compute_diff([spec("spec:A")], [impl("flag:F")], [test("L1:.:a.go")],
                           [feature("f", ["spec:A"], ["flag:F"], ["L1:.:ghost.go"])])
        self.assertEqual(["L1:.:ghost.go"], [d.atom_id for d in rep.dangling])

    def test_dangling_reference_does_not_mark_anything_claimed(self):
        rep = compute_diff([spec("spec:A")], [impl("flag:F")], [test("L1:.:a.go")],
                           [feature("f", ["spec:A", "spec:BOGUS"], ["flag:F"], ["L1:.:a.go"])])
        self.assertEqual([], rep.a_only)          # spec:A really was claimed
        self.assertEqual(1, len(rep.dangling))    # spec:BOGUS is a data error


class TestCoverageMath(unittest.TestCase):
    def test_percentages(self):
        rep = compute_diff(
            [spec("spec:A"), spec("spec:B"), spec("spec:C"), spec("spec:D")],
            [impl("flag:F")], [],
            [feature("f", ["spec:A"], ["flag:F"], ["L1:.:a.go"])],
        )
        claimed, total, pct = rep.coverage("spec")
        self.assertEqual((1, 4), (claimed, total))
        self.assertAlmostEqual(25.0, pct)
        self.assertEqual(0, rep.total("test"))

    def test_coverage_of_empty_set_is_zero_not_crash(self):
        rep = compute_diff([], [], [], [])
        self.assertEqual((0, 0, 0.0), rep.coverage("spec"))


class TestGrouping(unittest.TestCase):
    def test_group_by_kind(self):
        atoms = [impl("flag:A"), impl("flag:B"), impl("obj:x86:asm6.go", "obj")]
        got = group_by_kind(atoms)
        self.assertEqual({"flag": 2, "obj": 1}, {k: len(v) for k, v in got.items()})

    def test_test_group_bucketing(self):
        self.assertEqual("L1:fixedbugs", test_group("L1:fixedbugs:bug1.go"))
        self.assertEqual("L2:codegen", test_group("L2:codegen:addrcalc.go"))
        self.assertEqual("L5:script", test_group("L5:linkname.txt"))
        self.assertEqual("L3", test_group("L3:internal/test"))


class TestRendering(unittest.TestCase):
    def setUp(self):
        self.rep = compute_diff(
            [spec("spec:A"), spec("spec:B")],
            [impl("flag:F")],
            [test("L1:.:a.go")],
            [feature("f", ["spec:A"], ["flag:F"], ["L1:.:a.go"], ["L1:.:a.go"])],
        )

    def test_text_report_has_all_sections(self):
        out = render_text(self.rep, full=True)
        for marker in ("[0] dangling", "[1] A-only", "[2] B-only", "[3] C-only",
                       "VERDICT"):
            self.assertIn(marker, out)
        self.assertIn("spec:B", out)

    def test_verdict_fails_on_dangling(self):
        rep = compute_diff([spec("spec:A")], [impl("flag:F")], [test("L1:.:a.go")],
                           [feature("f", ["spec:GHOST"], ["flag:F"], ["L1:.:a.go"])])
        self.assertIn("VERDICT: FAIL", render_text(rep, full=True))

    def test_truncation_respects_top(self):
        atoms = [spec(f"spec:{i}") for i in range(30)]
        rep = compute_diff(atoms, [], [], [])
        out = render_text(rep, top=3, full=False)
        self.assertIn("... 27 more", out)
        self.assertNotIn("spec:29", out)

    def test_json_payload_shape(self):
        data = json.loads(render_json(self.rep))
        self.assertEqual({"spec": 2, "impl": 1, "test": 1, "features": 1}, data["baseline"])
        self.assertEqual(["spec:B"], [a["atom_id"] for a in data["zones"]["A-only"]])
        self.assertEqual([], data["dangling"])
        self.assertEqual(1, data["red_total"])


class TestCliEndToEnd(unittest.TestCase):
    """Write a tiny coverage dir and drive main() exactly as the shell would."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        (self.dir / "spec_atoms.toml").write_text(
            '[[spec_atoms]]\natom_id = "spec:A"\nkind = "h2"\nline = 1\n'
            'source_path = "x"\n\n[[spec_atoms]]\natom_id = "spec:B"\nkind = "h3"\nline = 2\n'
            'source_path = "x"\n', encoding="utf-8")
        (self.dir / "impl_atoms.toml").write_text(
            '[[impl_atoms]]\natom_id = "flag:F"\nkind = "flag"\nname = "F"\n'
            'source_path = "x"\nline = 1\n', encoding="utf-8")
        (self.dir / "official-tests.toml").write_text(
            '[[test_atoms]]\ntest_id = "L1:.:a.go"\nlayer = "L1"\nsource_path = "x"\nline = 1\n',
            encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def _write_features(self, body: str) -> Path:
        p = self.dir / "features.toml"
        p.write_text(body, encoding="utf-8")
        return p

    def _run(self, *argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(list(argv))
        return code, buf.getvalue()

    def test_clean_run_exits_zero(self):
        self._write_features(
            '[[features]]\nfeature_id = "f"\nspec_atoms = ["spec:A"]\n'
            'impl_atoms = ["flag:F"]\ntest_ids = ["L1:.:a.go"]\n'
            'negative_test_ids = ["L1:.:a.go"]\nmain_task = "M0.1"\n')
        code, out = self._run("--coverage-dir", str(self.dir))
        self.assertEqual(0, code)
        self.assertIn("spec:B", out)          # unclaimed clause surfaced
        self.assertIn("VERDICT: OK", out)

    def test_dangling_run_exits_one(self):
        self._write_features(
            '[[features]]\nfeature_id = "f"\nspec_atoms = ["spec:GHOST"]\n'
            'impl_atoms = ["flag:F"]\ntest_ids = ["L1:.:a.go"]\n'
            'negative_test_ids = ["L1:.:a.go"]\nmain_task = "M0.1"\n')
        code, out = self._run("--coverage-dir", str(self.dir))
        self.assertEqual(1, code)
        self.assertIn("spec:GHOST", out)
        self.assertIn("VERDICT: FAIL", out)

    def test_json_mode_is_parseable(self):
        self._write_features(
            '[[features]]\nfeature_id = "f"\nspec_atoms = ["spec:A"]\n'
            'impl_atoms = ["flag:F"]\ntest_ids = ["L1:.:a.go"]\n'
            'negative_test_ids = ["L1:.:a.go"]\nmain_task = "M0.1"\n')
        code, out = self._run("--coverage-dir", str(self.dir), "--json")
        self.assertEqual(0, code)
        data = json.loads(out)
        self.assertEqual(["spec:B"], [a["atom_id"] for a in data["zones"]["A-only"]])

    def test_out_writes_report_file(self):
        self._write_features(
            '[[features]]\nfeature_id = "f"\nspec_atoms = ["spec:A"]\n'
            'impl_atoms = ["flag:F"]\ntest_ids = ["L1:.:a.go"]\n'
            'negative_test_ids = ["L1:.:a.go"]\nmain_task = "M0.1"\n')
        out_path = self.dir / "report.txt"
        code, _ = self._run("--coverage-dir", str(self.dir), "--out", str(out_path))
        self.assertEqual(0, code)
        self.assertIn("triangle diff", out_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
