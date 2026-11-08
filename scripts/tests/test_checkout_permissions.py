import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from eqm_checkout import CheckoutError, assert_checkout_writable, checkout_paths, permission_issues
from eqm_update_agent import Agent, UpdateFailed


class CheckoutPermissions(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.root = self.folder / "checkout"
        self.root.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.email", "synthetic@example.invalid")
        self.git("config", "user.name", "Synthetic Test")
        (self.root / "frontend/src/feature").mkdir(parents=True)
        (self.root / "docs").mkdir()
        (self.root / "scripts").mkdir()
        (self.root / "frontend/src/feature/code.txt").write_text("old source\n")
        (self.root / "docs/notes.md").write_text("old docs\n")
        (self.root / ".gitignore").write_text(".env\nsde/\n.eqm-update/\n")
        shutil.copyfile(SCRIPTS / "eqm_checkout.py", self.root / "scripts/eqm_checkout.py")
        self.git("add", ".")
        self.git("commit", "-m", "Initial synthetic source")

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, stderr=subprocess.PIPE).decode().strip()

    def test_scan_is_bounded_to_tracked_source_and_git(self):
        (self.root / ".env").write_text("synthetic runtime config")
        (self.root / "sde").mkdir()
        (self.root / "sde/runtime.dat").write_text("synthetic volume")
        paths = set(checkout_paths(self.root))
        self.assertIn(self.root / "frontend/src/feature", paths)
        self.assertIn(self.root / ".git/index", paths)
        self.assertNotIn(self.root / ".env", paths)
        self.assertNotIn(self.root / "sde", paths)
        self.assertEqual(permission_issues(self.root), [])

    def test_missing_tracked_file_is_left_to_clean_tree_check(self):
        (self.root / "docs/notes.md").unlink()
        self.assertEqual(permission_issues(self.root), [])

    @unittest.skipUnless(os.name == "posix", "POSIX permissions")
    def test_readonly_source_parent_is_reported(self):
        path = self.root / "frontend/src/feature"
        path.chmod(0o555)
        self.addCleanup(path.chmod, 0o755)
        self.assertTrue(any("frontend/src/feature" in issue for issue in permission_issues(self.root)))

    @unittest.skipUnless(os.name == "posix", "POSIX permissions")
    def test_readonly_git_ref_file_is_reported(self):
        path = self.root / ".git/FETCH_HEAD"
        path.touch()
        path.chmod(0o444)
        self.addCleanup(path.chmod, 0o644)
        self.assertTrue(any("FETCH_HEAD" in issue for issue in permission_issues(self.root)))

    @unittest.skipUnless(os.name == "posix", "POSIX symlinks")
    def test_tracked_file_link_never_adds_its_target(self):
        outside = self.folder / "outside"
        outside.write_text("outside fixture")
        (self.root / "reference").symlink_to(outside)
        self.git("add", "reference")
        paths = set(checkout_paths(self.root))
        self.assertIn(self.root / "reference", paths)
        self.assertNotIn(outside, paths)

    @unittest.skipUnless(os.name == "posix", "POSIX symlinks")
    def test_linked_source_parent_is_rejected(self):
        source = self.root / "frontend/src/feature"
        outside = self.folder / "moved-feature"
        source.rename(outside)
        source.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(CheckoutError, "Linked source directory"):
            checkout_paths(self.root)

    @unittest.skipUnless(os.name == "posix", "POSIX symlinks")
    def test_linked_metadata_is_rejected(self):
        (self.root / ".git/linked").symlink_to(self.folder)
        with self.assertRaisesRegex(CheckoutError, "Linked Git metadata"):
            checkout_paths(self.root)

    def test_agent_stops_before_fetch_or_merge_and_keeps_actionable_reason(self):
        agent = Agent(self.root, "http://127.0.0.1:5173")
        with patch("eqm_update_agent.assert_checkout_writable", side_effect=CheckoutError("Checkout permissions: synthetic owner mismatch")), patch.object(agent, "command") as command:
            with self.assertRaisesRegex(UpdateFailed, "synthetic owner mismatch"):
                agent.update("a" * 32, None)
        command.assert_not_called()

    @unittest.skipUnless(os.name == "posix", "POSIX root guard")
    def test_root_updates_are_rejected(self):
        with patch("eqm_checkout.os.geteuid", return_value=0):
            with self.assertRaisesRegex(CheckoutError, "without sudo or root"):
                assert_checkout_writable(self.root)

    @unittest.skipUnless(os.name == "nt", "Windows batch integration")
    def test_windows_batch_propagates_permission_check_failure(self):
        (self.root / "scripts/eqm_checkout.py").write_text("raise SystemExit('Synthetic checkout permission failure')\n")
        old = self.git("rev-parse", "HEAD")
        env = {**os.environ, "EQM_UPDATE_ROOT": str(self.root), "EQM_UPDATE_PYTHON": sys.executable}
        result = subprocess.run(["cmd.exe", "/d", "/c", str(SCRIPTS.parent / "update-eqm.bat")], env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Synthetic checkout permission failure", result.stderr)
        self.assertNotIn("Rebuilding", result.stdout)
        self.assertEqual(self.git("rev-parse", "HEAD"), old)

    @unittest.skipUnless(os.name == "posix", "POSIX shell integration")
    def test_shell_blocks_partial_merge_then_succeeds_after_access_restored(self):
        old = self.git("rev-parse", "HEAD")
        (self.root / "frontend/src/feature/code.txt").write_text("new source\n")
        (self.root / "docs/notes.md").write_text("new docs\n")
        self.git("add", ".")
        self.git("commit", "-m", "New synthetic source and docs")
        target = self.git("rev-parse", "HEAD")
        self.git("reset", "--hard", old)
        binaries = self.folder / "bin"
        binaries.mkdir()
        marker = self.folder / "docker-called"
        docker = binaries / "docker"
        docker.write_text('#!/bin/sh\n: > "$EQM_TEST_DOCKER_MARKER"\nexit 0\n')
        docker.chmod(0o755)
        parent = self.root / "frontend/src/feature"
        parent.chmod(0o555)
        self.addCleanup(parent.chmod, 0o755)
        env = {**os.environ, "PATH": str(binaries) + os.pathsep + os.environ["PATH"], "EQM_UPDATE_ROOT": str(self.root), "EQM_UPDATE_TARGET": target, "EQM_UPDATE_PYTHON": sys.executable, "EQM_TEST_DOCKER_MARKER": str(marker)}
        script = SCRIPTS.parent / "update-eqm.sh"
        result = subprocess.run(["sh", str(script)], env=env, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Checkout permissions", result.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD"), old)
        self.assertEqual((self.root / "docs/notes.md").read_text(), "old docs\n")
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertFalse(marker.exists())
        parent.chmod(0o755)
        result = subprocess.run(["sh", str(script)], env=env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD"), target)
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertTrue(marker.exists())


if __name__ == "__main__":
    unittest.main()
