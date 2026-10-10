"""Keep preflight useful without flooding each cloud run's context."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from excalibur_blog_doctor import check  # noqa: E402


class DoctorOutputTest(unittest.TestCase):
    def test_passes_are_quiet_but_failures_remain_visible(self) -> None:
        errors: list[str] = []
        warnings: list[str] = []
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            check(True, "present", errors, warnings)
            check(False, "missing", errors, warnings)
            check(False, "caution", errors, warnings, warn=True)
        self.assertEqual(output.getvalue().splitlines(), ["FAIL missing", "WARN caution"])
        self.assertEqual(errors, ["missing"])
        self.assertEqual(warnings, ["caution"])

    def test_verbose_restores_passes(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            check(True, "present", [], [], verbose=True)
        self.assertEqual(output.getvalue(), "OK present\n")

    def test_environment_install_does_not_repeat_doctor(self) -> None:
        environment = json.loads((ROOT / ".cursor/environment.json").read_text(encoding="utf-8"))
        self.assertNotIn("excalibur_blog_doctor.py", environment["install"])
        automation = (ROOT / "CLOUD-AUTOMATION.md").read_text(encoding="utf-8")
        self.assertIn("python3 scripts/excalibur_blog_doctor.py", automation)


if __name__ == "__main__":
    unittest.main()
