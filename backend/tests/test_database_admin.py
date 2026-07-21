import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from fastapi import HTTPException

from app.api.auth import protect_host_assignment, require_host
from app.models import User
from app.services.database_admin import (
    BACKUP_FILENAME,
    BACKUP_FORMAT,
    MANIFEST_FILENAME,
    DatabaseAdminError,
    inspect_backup,
)
from app.services.permissions import ROLE_RANK, default_section_allowed, role_rank


class HostRoleTests(unittest.TestCase):
    def test_host_ranks_above_admin_and_can_view_sections(self) -> None:
        self.assertGreater(ROLE_RANK["host"], ROLE_RANK["admin"])
        self.assertEqual(role_rank("host"), ROLE_RANK["host"])
        self.assertTrue(default_section_allowed("host", "audit"))

    def test_host_only_guard_rejects_admin(self) -> None:
        admin = User(email="admin@example.test", display_name="Admin", role="admin")
        with self.assertRaises(HTTPException):
            require_host(admin)
        with self.assertRaises(HTTPException):
            protect_host_assignment(admin, "host")

    def test_host_can_assign_host(self) -> None:
        host = User(email="host@example.test", display_name="Host", role="host")
        require_host(host)
        protect_host_assignment(host, "host")


class BackupManifestTests(unittest.TestCase):
    def make_archive(self, root: Path, *, revision: str = "0047_host_role", contains_host: bool = True) -> Path:
        path = root / "backup.eqmbackup"
        manifest = {
            "format": BACKUP_FORMAT,
            "schema_revision": revision,
            "contains_host": contains_host,
        }
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(MANIFEST_FILENAME, json.dumps(manifest))
            archive.writestr(BACKUP_FILENAME, b"postgres archive")
        return path

    def test_valid_manifest_extracts_database_dump(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive = self.make_archive(Path(temporary))
            manifest, dump_path = inspect_backup(archive, "0047_host_role")
            self.assertEqual(manifest["format"], BACKUP_FORMAT)
            self.assertEqual(dump_path.read_bytes(), b"postgres archive")

    def test_schema_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive = self.make_archive(Path(temporary), revision="0046_research_queue")
            with self.assertRaisesRegex(DatabaseAdminError, "does not match"):
                inspect_backup(archive, "0047_host_role")

    def test_backup_without_host_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive = self.make_archive(Path(temporary), contains_host=False)
            with self.assertRaisesRegex(DatabaseAdminError, "host account"):
                inspect_backup(archive, "0047_host_role")


if __name__ == "__main__":
    unittest.main()
