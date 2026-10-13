#!/usr/bin/env python3
"""Cert guard rejects a planted .bks file and ignores the same bytes as .txt.

The upload exclusion for that suffix is the workflow line
`!/tmp/mdm-ci/**/*.bks`. The guard lists `-name '*.bks'` in
scripts/lib/cert-guard.sh. No emulator.
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "scripts" / "lib" / "cert-guard.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "emulator-policy.yml"


class CertGuardTest(unittest.TestCase):
    def _hits(self, root: Path) -> str:
        proc = subprocess.run(
            [
                "bash",
                "-c",
                'set -euo pipefail; source "$1"; cert_guard_hits "$2"',
                "bash",
                str(LIB),
                str(root),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def test_bks_file_is_rejected_and_txt_is_not(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            planted = root / "secret.bks"
            planted.write_bytes(b"not-a-real-keystore")
            hits = self._hits(root)
            self.assertIn("secret.bks", hits)
            planted.rename(root / "secret.txt")
            self.assertNotIn("secret", self._hits(root))

    def test_certs_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested = root / "leg" / "certs"
            nested.mkdir(parents=True)
            (nested / "ca.pem").write_text("not-a-real-cert\n", encoding="utf-8")
            hits = self._hits(root)
            self.assertIn("ca.pem", hits)
            self.assertIn(str(nested), hits)

    def test_workflow_and_guard_each_name_bks(self) -> None:
        workflow_lines = [line.strip() for line in WORKFLOW.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(workflow_lines.count("!/tmp/mdm-ci/**/*.bks"), 1)
        guard_lines = [line.strip() for line in LIB.read_text(encoding="utf-8").splitlines()]
        self.assertIn("-o -name '*.bks' \\", guard_lines)


if __name__ == "__main__":
    unittest.main()
