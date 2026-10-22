"""Tes model & persistensi Shelf (tanpa UI)."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from notchy.shelf import (  # noqa: E402
    SCHEMA_VERSION,
    ShelfModel,
    ShelfStore,
    normalize_path,
)


class ShelfTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.store_path = os.path.join(self.dir, "shelf.json")
        self.model = ShelfModel(ShelfStore(self.store_path))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def make_file(self, name: str = "file.txt", content: str = "x") -> str:
        path = os.path.join(self.dir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path


class TestModel(ShelfTestBase):
    def test_empty_start(self):
        self.assertTrue(self.model.is_empty)
        self.assertEqual(self.model.items, [])

    def test_add_single_file(self):
        path = self.make_file()
        added, skipped = self.model.add_paths([path])
        self.assertEqual(len(added), 1)
        self.assertEqual(skipped, 0)
        self.assertFalse(self.model.is_empty)
        self.assertTrue(os.path.exists(self.model.items[0].path))

    def test_add_multiple_files(self):
        a = self.make_file("a.txt")
        b = self.make_file("b.txt")
        added, skipped = self.model.add_paths([a, b])
        self.assertEqual(len(added), 2)
        self.assertEqual(skipped, 0)

    def test_duplicate_path_skipped(self):
        path = self.make_file()
        self.model.add_paths([path])
        added, skipped = self.model.add_paths([path, path])
        self.assertEqual(added, [])
        self.assertEqual(skipped, 2)
        self.assertEqual(len(self.model.items), 1)

    def test_normalized_duplicate(self):
        path = self.make_file()
        messy = os.path.join(self.dir, ".", "sub", "..", "file.txt")
        self.model.add_paths([path])
        added, _ = self.model.add_paths([messy])
        self.assertEqual(added, [])
        self.assertEqual(len(self.model.items), 1)

    def test_spaces_and_unicode(self):
        path = self.make_file("laporan akhir – résumé 日本語.txt")
        added, _ = self.model.add_paths([path])
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0].name, os.path.basename(path))

    def test_add_folder(self):
        folder = os.path.join(self.dir, "Folder Saya")
        os.makedirs(folder)
        added, _ = self.model.add_paths([folder])
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0].kind, "dir")

    def test_nonexistent_rejected(self):
        missing = os.path.join(self.dir, "tidak-ada.txt")
        added, skipped = self.model.add_paths([missing])
        self.assertEqual(added, [])
        self.assertEqual(skipped, 1)

    def test_remove_keeps_original_file(self):
        path = self.make_file()
        self.model.add_paths([path])
        item_id = self.model.items[0].id
        self.assertTrue(self.model.remove(item_id))
        self.assertTrue(os.path.exists(path))
        self.assertEqual(self.model.items, [])

    def test_missing_file_stays_and_recovers(self):
        path = self.make_file()
        self.model.add_paths([path])
        item = self.model.items[0]
        os.remove(path)
        self.assertFalse(item.exists())
        # muat ulang: item tetap ada
        reloaded = ShelfModel(ShelfStore(self.store_path))
        self.assertEqual(len(reloaded.items), 1)
        self.assertFalse(reloaded.items[0].exists())
        # file kembali → tersedia lagi
        with open(path, "w", encoding="utf-8") as f:
            f.write("kembali")
        self.assertTrue(reloaded.items[0].exists())

    def test_symlink_distinct_paths(self):
        target = self.make_file("target.txt")
        link = os.path.join(self.dir, "link.txt")
        os.symlink(target, link)
        added, _ = self.model.add_paths([target, link])
        self.assertEqual(len(added), 2)  # kebijakan: symlink tidak di-resolve

    def test_normalize_policy(self):
        self.assertEqual(normalize_path("~/"), os.path.expanduser("~"))
        self.assertEqual(normalize_path("a/../b"), os.path.abspath("b"))


class TestPersistence(ShelfTestBase):
    def test_reload_after_restart(self):
        a = self.make_file("a.txt")
        b = self.make_file("b.txt")
        self.model.add_paths([a, b])
        reloaded = ShelfModel(ShelfStore(self.store_path))
        self.assertEqual([i.path for i in reloaded.items],
                         [normalize_path(a), normalize_path(b)])

    def test_schema_version_written(self):
        self.model.add_paths([self.make_file()])
        with open(self.store_path, encoding="utf-8") as f:
            doc = json.load(f)
        self.assertEqual(doc["version"], SCHEMA_VERSION)
        self.assertIsInstance(doc["items"], list)

    def test_corrupt_json_backup_and_safe_start(self):
        with open(self.store_path, "w", encoding="utf-8") as f:
            f.write("{ ini bukan json")
        model = ShelfModel(ShelfStore(self.store_path))
        self.assertEqual(model.items, [])
        self.assertEqual(model.load_status, "corrupt")
        backups = [n for n in os.listdir(self.dir) if ".corrupt-" in n]
        self.assertTrue(backups, "cadangan file rusak harus dibuat")

    def test_unsupported_version_backup(self):
        with open(self.store_path, "w", encoding="utf-8") as f:
            json.dump({"version": 99, "items": []}, f)
        model = ShelfModel(ShelfStore(self.store_path))
        self.assertEqual(model.load_status, "unsupported")
        backups = [n for n in os.listdir(self.dir) if ".unsupported-" in n]
        self.assertTrue(backups)

    def test_partial_invalid_items(self):
        with open(self.store_path, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "items": [
                {"path": self.make_file("ok.txt")},
                {"bukan": "item"},
            ]}, f)
        model = ShelfModel(ShelfStore(self.store_path))
        self.assertEqual(len(model.items), 1)
        self.assertEqual(model.load_status, "partial")

    def test_write_failure_keeps_old_file(self):
        path = self.make_file()
        self.model.add_paths([path])
        with open(self.store_path, encoding="utf-8") as f:
            old = f.read()
        with mock.patch("os.replace", side_effect=OSError("disk penuh")):
            ok = self.model.store.save(self.model.items)
        self.assertFalse(ok)
        with open(self.store_path, encoding="utf-8") as f:
            self.assertEqual(f.read(), old)  # file lama utuh

    def test_remove_persists(self):
        path = self.make_file()
        self.model.add_paths([path])
        item_id = self.model.items[0].id
        self.model.remove(item_id)
        reloaded = ShelfModel(ShelfStore(self.store_path))
        self.assertEqual(reloaded.items, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)