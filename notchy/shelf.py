"""Model & persistensi Rak Berkas (File Shelf).

Terpisah dari UI: hanya data, normalisasi path, dan JSON store atomik.
Lokasi data: ~/.local/share/notchy/shelf.json (bukan cache).
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass

log = logging.getLogger("notchy.shelf")

DATA_DIR = os.path.join(os.path.expanduser("~"), ".local", "share", "notchy")
SHELF_PATH = os.path.join(DATA_DIR, "shelf.json")
SCHEMA_VERSION = 1

KIND_FILE = "file"
KIND_DIR = "dir"


def normalize_path(path: str) -> str:
    """Path absolut kanonik-teks: expanduser + normpath + abspath.

    Symlink TIDAK di-resolve (realpath) agar dua referensi yang berbeda
    tetap dianggap berbeda — kebijakan eksplisit. Duplikat hanya terjadi
    bila teks path ternormalisasi identik.
    """
    p = os.path.expanduser(str(path))
    p = os.path.abspath(os.path.normpath(p))
    return p


@dataclass
class ShelfItem:
    id: str
    path: str
    name: str
    kind: str = KIND_FILE
    size: int = 0
    mtime: float = 0.0

    # ------------------------------------------------------------ runtime
    def exists(self) -> bool:
        return os.path.exists(self.path)

    def refresh_meta(self) -> None:
        try:
            st = os.stat(self.path)
            self.size = int(st.st_size)
            self.mtime = float(st.st_mtime)
            self.kind = KIND_DIR if os.path.isdir(self.path) else KIND_FILE
        except OSError:
            # tetap simpan item; status missing dihitung saat tampil
            pass

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "path": self.path,
            "name": self.name,
            "kind": self.kind,
            "size": self.size,
            "mtime": self.mtime,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ShelfItem | None":
        try:
            path = normalize_path(str(d["path"]))
            item_id = str(d.get("id") or uuid.uuid4().hex)
            name = str(d.get("name") or os.path.basename(path) or path)
            kind = str(d.get("kind") or KIND_FILE)
            if kind not in (KIND_FILE, KIND_DIR):
                kind = KIND_FILE
            return cls(
                id=item_id,
                path=path,
                name=name,
                kind=kind,
                size=int(d.get("size") or 0),
                mtime=float(d.get("mtime") or 0.0),
            )
        except Exception:
            return None


class ShelfStore:
    """JSON store atomik dengan penanganan korupsi yang aman."""

    def __init__(self, path: str | None = None) -> None:
        self.path = path or SHELF_PATH

    # ------------------------------------------------------------ load
    def load(self) -> tuple[list[ShelfItem], str]:
        """Kembalikan (items, status).

        status: "" (ok/missing file), "corrupt", "unsupported", "partial".
        File rusak TIDAK ditimpa kosong; dibuat cadangan .corrupt-<ts>.
        """
        if not os.path.isfile(self.path):
            return [], ""
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                doc = json.load(f)
        except Exception as exc:
            log.error("shelf.json rusak: %s", exc)
            self._backup("corrupt")
            return [], "corrupt"

        if not isinstance(doc, dict):
            log.error("shelf.json bukan objek JSON")
            self._backup("corrupt")
            return [], "corrupt"

        version = doc.get("version", 0)
        try:
            version = int(version)
        except Exception:
            version = 0
        if version > SCHEMA_VERSION:
            log.error("shelf.json versi %s tidak didukung (maks %s)", version, SCHEMA_VERSION)
            self._backup("unsupported")
            return [], "unsupported"

        raw_items = doc.get("items") or []
        items: list[ShelfItem] = []
        invalid = 0
        seen: set[str] = set()
        for raw in raw_items:
            item = ShelfItem.from_dict(raw) if isinstance(raw, dict) else None
            if item is None:
                invalid += 1
                continue
            if item.path in seen:
                invalid += 1
                continue
            seen.add(item.path)
            items.append(item)
        if invalid:
            log.warning("shelf.json: %d entri tidak valid dilewati", invalid)
            return items, "partial"
        return items, ""

    def _backup(self, reason: str) -> None:
        try:
            stamp = time.strftime("%Y%m%d-%H%M%S")
            with open(self.path, "rb") as src:
                data = src.read()
            backup = f"{self.path}.{reason}-{stamp}"
            with open(backup, "wb") as dst:
                dst.write(data)
            log.error("cadangan shelf dibuat: %s", backup)
        except Exception as exc:
            log.error("gagal membuat cadangan shelf: %s", exc)

    # ------------------------------------------------------------ save
    def save(self, items: list[ShelfItem]) -> bool:
        """Tulis atomik: file sementara → os.replace. Return sukses."""
        doc = {
            "version": SCHEMA_VERSION,
            "items": [item.to_dict() for item in items],
        }
        tmp = f"{self.path}.tmp-{os.getpid()}"
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
            return True
        except Exception as exc:
            log.error("gagal menyimpan shelf: %s", exc)
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
            return False


class ShelfModel:
    """Daftar referensi item. Tidak pernah menyentuh file asli."""

    def __init__(self, store: ShelfStore | None = None) -> None:
        self.store = store or ShelfStore()
        self.items: list[ShelfItem] = []
        self.load_status = ""
        self.load()

    # ------------------------------------------------------------ queries
    @property
    def is_empty(self) -> bool:
        return not self.items

    def get(self, item_id: str) -> ShelfItem | None:
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def has_path(self, path: str) -> bool:
        norm = normalize_path(path)
        return any(item.path == norm for item in self.items)

    # ------------------------------------------------------------ mutate
    def add_paths(self, paths: list[str]) -> tuple[list[ShelfItem], int]:
        """Tambah referensi. Return (added, skipped).

        - Hanya path yang benar-benar ada saat ini yang diterima.
        - Duplikat (path ternormalisasi sama) dilewati, termasuk dalam batch.
        - Simpan sekali di akhir (batch).
        """
        added: list[ShelfItem] = []
        skipped = 0
        for raw in paths:
            try:
                path = normalize_path(raw)
            except Exception:
                skipped += 1
                continue
            if not os.path.exists(path):
                skipped += 1
                continue
            if any(item.path == path for item in self.items) or any(
                item.path == path for item in added
            ):
                skipped += 1
                continue
            item = ShelfItem(
                id=uuid.uuid4().hex,
                path=path,
                name=os.path.basename(path) or path,
                kind=KIND_DIR if os.path.isdir(path) else KIND_FILE,
            )
            item.refresh_meta()
            added.append(item)
        if added:
            self.items.extend(added)
            self.store.save(self.items)
        return added, skipped

    def remove(self, item_id: str) -> bool:
        for i, item in enumerate(self.items):
            if item.id == item_id:
                del self.items[i]
                self.store.save(self.items)
                return True
        return False

    def refresh(self) -> None:
        """Perbarui metadata/status; file hilang tetap tercatat."""
        for item in self.items:
            if item.exists():
                item.refresh_meta()

    # ------------------------------------------------------------ persist
    def load(self) -> None:
        items, status = self.store.load()
        self.items = items
        self.load_status = status

    def save(self) -> bool:
        return self.store.save(self.items)