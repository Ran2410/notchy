"""Tes UI Shelf (offscreen): aturan tab, scroll, drop invalid, drag-out mime."""
import os
import sys
import tempfile
import unittest

# isolasi HOME sebelum modul notchy diimpor (SHELF_PATH dihitung saat import)
_TMP_HOME = tempfile.mkdtemp(prefix="notchy-home-")
os.environ["HOME"] = _TMP_HOME
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QDropEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from notchy.shelf import ShelfItem, ShelfModel, ShelfStore  # noqa: E402
from notchy.ui.island import IslandWindow  # noqa: E402
from notchy.ui.shelf import ShelfRow  # noqa: E402

_app = None


def files_dir() -> str:
    d = os.path.join(_TMP_HOME, "files")
    os.makedirs(d, exist_ok=True)
    return d


def make_file(name: str = "file.txt") -> str:
    p = os.path.join(files_dir(), name)
    with open(p, "w", encoding="utf-8") as f:
        f.write("x" * 1000)
    return p


class ShelfUITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global _app
        _app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        # store terisolasi per tes (tidak menyentuh data pengguna)
        self.store_path = os.path.join(_TMP_HOME, f"shelf-{id(self)}.json")
        try:
            os.remove(self.store_path)
        except FileNotFoundError:
            pass
        model = ShelfModel(ShelfStore(self.store_path))
        self.win = IslandWindow(shelf=model)
        self.win.show()
        self.activities = self.win.activities
        self.win._poll_media.stop()

    def tearDown(self):
        self.win.close()
        self.win.deleteLater()
        QTest.qWait(50)

    # ------------------------------------------------------------ helpers
    def tab(self) -> int:
        return self.activities._tab_index

    def process(self, ms: int = 500) -> None:
        QTest.qWait(ms)

    # ------------------------------------------------------------ tests
    def test_first_drop_switches_to_shelf_and_expands(self):
        path = make_file()
        self.win._apply_drop([path])
        self.process(900)
        self.assertEqual(self.tab(), 3)
        self.assertGreater(self.win._t, 0.9)
        self.assertEqual(len(self.win.shelf.items), 1)
        self.assertFalse(self.activities.shelf_page.empty.isVisible())

    def test_second_drop_keeps_current_tab(self):
        self.win._apply_drop([make_file("a.txt")])
        self.process(800)
        self.activities._set_tab(0)
        self.process(600)
        self.assertEqual(self.tab(), 0)
        self.win._apply_drop([make_file("b.txt")])
        self.process(700)
        self.assertEqual(self.tab(), 0)          # tidak dipaksa pindah
        self.assertEqual(len(self.win.shelf.items), 2)

    def test_scroll_preserved_when_adding_on_shelf(self):
        many = [make_file(f"file-{i:02d}.txt") for i in range(24)]
        self.win._apply_drop(many)
        self.process(900)
        self.activities.switch_to_shelf()
        self.process(600)
        bar = self.activities.shelf_page.scroll.verticalScrollBar()
        bar.setValue(150)
        self.process(100)
        before = bar.value()
        self.win._apply_drop([make_file("baru.txt")])
        self.process(700)
        self.assertEqual(bar.value(), before)
        self.assertEqual(len(self.win.shelf.items), 25)

    def test_invalid_drop_does_not_switch_or_add(self):
        mime = QMimeData()
        mime.setText("bukan file")
        ev = QDropEvent(QPointF(10, 10), Qt.CopyAction, mime,
                        Qt.LeftButton, Qt.NoModifier)
        self.win.dropEvent(ev)
        self.process(400)
        self.assertEqual(self.tab(), 0)
        self.assertEqual(len(self.win.shelf.items), 0)
        self.assertEqual(self.activities._drop_overlay.state, "DRAG_OVER_INVALID")

    def test_dropped_files_batch_single_save(self):
        a = make_file("satu.txt")
        b = make_file("dua.txt")
        with unittest.mock.patch.object(
                self.win.shelf.store, "save", wraps=self.win.shelf.store.save) as spy:
            self.win._apply_drop([a, b])
            self.process(400)
        self.assertEqual(spy.call_count, 1)      # satu save untuk satu drop
        self.assertEqual(len(self.win.shelf.items), 2)

    def test_remove_keeps_original_file(self):
        path = make_file()
        self.win._apply_drop([path])
        self.process(700)
        item_id = self.win.shelf.items[0].id
        self.activities.shelf_page._remove_id(item_id)
        self.process(400)
        self.assertTrue(os.path.exists(path))
        self.assertEqual(len(self.win.shelf.items), 0)

    def test_missing_state_label(self):
        path = make_file("hilang.txt")
        self.win._apply_drop([path])
        self.process(700)
        os.remove(path)
        self.activities.shelf_page.refresh_states()
        row = self.activities.shelf_page._rows[self.win.shelf.items[0].id]
        self.assertEqual(row.meta_label.text(), "Missing")
        self.assertIn("0.35", row.name_label.styleSheet())

    def test_drag_out_mime_contains_local_url(self):
        path = make_file("seret.txt")
        item = ShelfItem(id="id1", path=path, name="seret.txt")
        row = ShelfRow(item)
        mime = row.drag_mime()
        self.assertTrue(mime.hasUrls())
        self.assertEqual(mime.urls()[0].toLocalFile(), path)
        row.deleteLater()


import unittest.mock  # noqa: E402

if __name__ == "__main__":
    unittest.main(verbosity=2)