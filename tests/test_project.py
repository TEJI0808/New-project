import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from modules.audit import process_audit_files, prune_old_archives, get_archive_summary
from modules.config import load_config, apply_cli_overrides, ConfigError
from modules.monitoring import check_storage


class FakeLogger:
    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspace = self.root / "audit"
        self.workspace.mkdir()
        self.config = {
            "general": {"authorized_user": "auditmanager"},
            "paths": {
                "workspace": str(self.workspace),
                "log_file": str(self.root / "sysaudit.log"),
                "state_file": str(self.root / "state.txt"),
                "delegation_file": str(self.root / "delegates.json"),
            },
            "storage": {
                "max_storage_mb": 100,
                "archive_retention_days": 14,
                "stop_on_limit": False,
            },
            "schedule": {"interval_days": 3},
        }
        self.logger = FakeLogger()

    def tearDown(self):
        self.temp.cleanup()

    def test_archives_audit_and_removes_source_after_success(self):
        source = self.workspace / "one.audit"
        source.write_text("sample audit data", encoding="utf-8")
        result = process_audit_files(self.config, self.logger)
        self.assertEqual(result["archived_count"], 1)
        self.assertFalse(source.exists())
        self.assertTrue(Path(result["archive_path"]).is_file())

    def test_no_source_files_is_safe(self):
        result = process_audit_files(self.config, self.logger)
        self.assertEqual(result["archived_count"], 0)

    def test_storage_check(self):
        (self.workspace / "data.txt").write_text("abc", encoding="utf-8")
        size, over = check_storage(self.config, self.logger)
        self.assertGreaterEqual(size, 3)
        self.assertFalse(over)

    def test_archive_summary(self):
        (self.workspace / "archives").mkdir()
        archive = self.workspace / "archives" / "example.tar.gz"
        archive.write_bytes(b"123456")
        summary = get_archive_summary(self.config, self.logger)
        self.assertEqual(summary["archive_count"], 1)
        self.assertEqual(summary["largest_name"], "example.tar.gz")
        self.assertEqual(summary["largest_size_bytes"], 6)

    def test_prunes_old_archive(self):
        import time
        archive_dir = self.workspace / "archives"
        archive_dir.mkdir()
        old = archive_dir / "old.tar.gz"
        old.write_bytes(b"old")
        old_time = time.time() - 20 * 24 * 60 * 60
        os.utime(old, (old_time, old_time))
        removed = prune_old_archives(self.config, self.logger)
        self.assertEqual(removed, 1)
        self.assertFalse(old.exists())

    def test_missing_config_fails(self):
        with self.assertRaises(FileNotFoundError):
            load_config(str(self.root / "missing.cfg"))


if __name__ == "__main__":
    unittest.main()
