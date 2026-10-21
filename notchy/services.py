"""Layanan Prioritas 2 — cuaca, agenda (ICS), watcher unduhan.

AgendaService dipertahankan untuk pemakaian mendatang (UI agenda saat ini
dihapus karena terlalu panjang).

Semua cross-platform (Linux & Windows), tanpa dependensi tambahan.
- Cuaca : Open-Meteo (tanpa API key) + geolokasi IP, cache di ~/.cache/notchy
- Agenda: parser ICS sederhana (VEVENT + RRULE DAILY/WEEKLY dasar)
- Unduhan: pantau folder Downloads untuk file yang sedang tumbuh / .part
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "notchy")
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".config", "notchy", "config.json")
UA = "notchy/0.3 (Linux/Windows; weather+agenda+downloads)"


# ---------------------------------------------------------------- util
def load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _http_json(url: str, timeout: float = 8.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read(512 * 1024).decode("utf-8", "replace"))


# ================================================================= CUACA
# kode WMO → (teks, simbol monokrom yang aman di font umum)
WMO = {
    0: ("Cerah", "☀"), 1: ("Cerah berawan", "☀"), 2: ("Berawan sebagian", "☁"),
    3: ("Mendung", "☁"), 45: ("Berkabut", "☁"), 48: ("Kabut beku", "☁"),
    51: ("Gerimis ringan", "☂"), 53: ("Gerimis", "☂"), 55: ("Gerimis lebat", "☂"),
    56: ("Gerimis beku", "❄"), 57: ("Gerimis beku", "❄"),
    61: ("Hujan ringan", "☂"), 63: ("Hujan", "☂"), 65: ("Hujan lebat", "☂"),
    66: ("Hujan beku", "❄"), 67: ("Hujan beku", "❄"),
    71: ("Salju ringan", "❄"), 73: ("Salju", "❄"), 75: ("Salju lebat", "❄"),
    77: ("Butiran salju", "❄"),
    80: ("Hujan lokal", "☂"), 81: ("Hujan lokal", "☂"), 82: ("Hujan deras", "☂"),
    85: ("Hujan salju", "❄"), 86: ("Hujan salju", "❄"),
    95: ("Badai petir", "⚡"), 96: ("Badai + hujan es", "⚡"), 99: ("Badai + hujan es", "⚡"),
}


@dataclass
class Weather:
    ok: bool = False
    temp: float = 0.0
    code: int = -1
    city: str = ""
    updated: float = 0.0
    hourly: list = field(default_factory=list)   # [(label, temp, code), ...]

    @property
    def text(self) -> str:
        return WMO.get(self.code, ("—", "·"))[0]

    @property
    def icon(self) -> str:
        return WMO.get(self.code, ("—", "·"))[1]


class WeatherService:
    """Fetch di background; UI memanggil poll() untuk membaca hasil."""

    def __init__(self) -> None:
        self._data = Weather()
        self._busy = False
        self._last_try = 0.0
        self._load_cache()

    @property
    def data(self) -> Weather:
        return self._data

    # ------------------------------------------------------------ cache
    def _cache_file(self) -> str:
        return os.path.join(CACHE_DIR, "weather.json")

    def _load_cache(self) -> None:
        try:
            with open(self._cache_file(), "r", encoding="utf-8") as f:
                d = json.load(f)
            self._data = Weather(
                ok=True, temp=float(d["temp"]), code=int(d["code"]),
                city=str(d.get("city", "")), updated=float(d.get("updated", 0)),
                hourly=[(str(h[0]), float(h[1]), int(h[2])) for h in d.get("hourly", [])],
            )
        except Exception:
            pass

    def _save_cache(self) -> None:
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            w = self._data
            with open(self._cache_file(), "w", encoding="utf-8") as f:
                json.dump({"temp": w.temp, "code": w.code, "city": w.city,
                           "updated": w.updated, "hourly": w.hourly}, f)
        except Exception:
            pass

    # ------------------------------------------------------------ fetch
    def refresh_async(self, max_age: float = 1800.0) -> None:
        now = time.time()
        # paksa fetch bila cache lama belum punya data per jam
        if self._busy or (self._data.ok and self._data.hourly
                          and now - self._data.updated < max_age):
            return
        if now - self._last_try < 60:
            return
        self._last_try = now
        self._busy = True
        threading.Thread(target=self._worker, daemon=True, name="notchy-weather").start()

    def _worker(self) -> None:
        try:
            lat, lon, city = self._location()
            if lat is None:
                return
            url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                   f"&current=temperature_2m,weather_code"
                   f"&hourly=temperature_2m,weather_code&forecast_days=2&timezone=auto")
            d = _http_json(url)
            cur = d.get("current") or {}
            hourly = []
            try:
                h = d.get("hourly") or {}
                times = h.get("time") or []
                temps = h.get("temperature_2m") or []
                codes = h.get("weather_code") or []
                now = _dt.datetime.now()
                for iso, tp, ccode in zip(times, temps, codes):
                    try:
                        dt = _dt.datetime.fromisoformat(iso)
                    except Exception:
                        continue
                    if dt < now.replace(minute=0, second=0, microsecond=0):
                        continue
                    hourly.append((dt.strftime("%H:00"), float(tp), int(ccode)))
                    if len(hourly) >= 5:
                        break
            except Exception:
                pass
            self._data = Weather(
                ok=True,
                temp=float(cur.get("temperature_2m", 0)),
                code=int(cur.get("weather_code", -1)),
                city=city,
                updated=time.time(),
                hourly=hourly,
            )
            self._save_cache()
        except Exception:
            pass
        finally:
            self._busy = False

    def _location(self):
        cfg = load_config().get("weather") or {}
        if cfg.get("lat") is not None and cfg.get("lon") is not None:
            return float(cfg["lat"]), float(cfg["lon"]), str(cfg.get("city", ""))
        # geolokasi IP (dua penyedia gratis, tanpa key)
        for url, pick in (
            ("https://ipapi.co/json/", lambda d: (d.get("latitude"), d.get("longitude"), d.get("city"))),
            ("http://ip-api.com/json/?fields=lat,lon,city", lambda d: (d.get("lat"), d.get("lon"), d.get("city"))),
        ):
            try:
                lat, lon, city = pick(_http_json(url))
                if lat is not None and lon is not None:
                    return float(lat), float(lon), str(city or "")
            except Exception:
                continue
        return None, None, ""


# ================================================================= AGENDA
@dataclass
class AgendaEvent:
    start: _dt.datetime
    end: _dt.datetime | None
    summary: str

    def starts_in(self, now: _dt.datetime | None = None) -> _dt.timedelta:
        now = now or _dt.datetime.now()
        return self.start - now


class AgendaService:
    """Parser ICS minimal. Cari file: config.calendar.paths, ~/.calendars/*.ics,
    ~/.local/share/notchy/*.ics."""

    def __init__(self) -> None:
        self.next_event: AgendaEvent | None = None
        self.upcoming: list[AgendaEvent] = []
        self.last_scan = 0.0

    def _paths(self) -> list[str]:
        paths = []
        cfg = load_config().get("calendar") or {}
        for p in cfg.get("paths") or []:
            paths.append(os.path.expanduser(p))
        for d in (
            "~/.calendars",
            "~/.local/share/notchy",
            # GNOME Calendar / Evolution (calendar sistem)
            "~/.local/share/evolution/calendar/system",
            "~/.local/share/evolution/calendar",
        ):
            d = os.path.expanduser(d)
            if os.path.isdir(d):
                for name in os.listdir(d):
                    if name.lower().endswith(".ics"):
                        paths.append(os.path.join(d, name))
        return [p for p in paths if os.path.isfile(p)]

    def refresh(self) -> AgendaEvent | None:
        now = _dt.datetime.now()
        events: list[AgendaEvent] = []
        for path in self._paths():
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except Exception:
                continue
            for ev in self._parse_ics(text, now):
                if ev.end and ev.end < now:
                    continue
                if ev.start < now - _dt.timedelta(minutes=1):
                    continue
                events.append(ev)
        events.sort(key=lambda e: e.start)
        # dedupe ringan (judul + waktu sama)
        seen = set()
        uniq = []
        for ev in events:
            key = (ev.summary, ev.start)
            if key in seen:
                continue
            seen.add(key)
            uniq.append(ev)
        self.upcoming = uniq[:5]
        self.next_event = uniq[0] if uniq else None
        self.last_scan = time.time()
        return self.next_event

    # ------------------------------------------------------------ parser
    @staticmethod
    def _parse_dt(raw: str) -> _dt.datetime | None:
        raw = raw.strip()
        for fmt in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M", "%Y%m%d"):
            try:
                return _dt.datetime.strptime(raw, fmt)
            except ValueError:
                continue
        return None

    def _parse_ics(self, text: str, now: _dt.datetime) -> list[AgendaEvent]:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # buka baris terlipat (RFC5545: baris lanjutan diawali spasi/tab)
        text = re.sub(r"\n[ \t]", "", text)
        out: list[AgendaEvent] = []
        for block in text.split("BEGIN:VEVENT")[1:]:
            fields: dict[str, str] = {}
            for line in block.split("\n"):
                if ":" not in line:
                    continue
                key, val = line.split(":", 1)
                name = key.split(";")[0].strip().upper()
                fields[name] = val.strip()
            dtstart = self._parse_dt(fields.get("DTSTART", ""))
            if dtstart is None:
                continue
            dtend = self._parse_dt(fields.get("DTEND", ""))
            summary = fields.get("SUMMARY", "(tanpa judul)")
            rrule = fields.get("RRULE", "")

            occurrences = [dtstart]
            if rrule and "FREQ" in rrule:
                step = None
                if "FREQ=DAILY" in rrule:
                    step = _dt.timedelta(days=1)
                elif "FREQ=WEEKLY" in rrule:
                    step = _dt.timedelta(weeks=1)
                if step:
                    occ = dtstart
                    for _ in range(370):
                        occ = occ + step
                        if occ > now + _dt.timedelta(days=14):
                            break
                        if occ >= now - _dt.timedelta(minutes=1):
                            occurrences.append(occ)
                            break
            for occ in occurrences:
                end = (occ + (dtend - dtstart)) if dtend else None
                out.append(AgendaEvent(start=occ, end=end, summary=summary))
        return out


# ================================================================= UNDUHAN
PARTIAL_EXTS = (".crdownload", ".part", ".tmp", ".download", ".opdownload", ".partial")


@dataclass
class Download:
    name: str
    path: str
    size: int = 0
    updated: float = 0.0


class DownloadsService:
    """Deteksi unduhan aktif: ekstensi parsial atau ukuran file yang membesar."""

    def __init__(self, directory: str | None = None) -> None:
        cfg = (load_config().get("downloads") or {}).get("dir")
        self.dir = os.path.expanduser(directory or cfg or "~/Downloads")
        self.active: dict[str, Download] = {}
        self.events: list[tuple[str, str]] = []   # ("started"|"finished", name)
        self._sizes: dict[str, int] = {}

    def scan(self) -> None:
        now = time.time()
        try:
            entries = list(os.scandir(self.dir))
        except Exception:
            return
        seen = set()
        for entry in entries:
            try:
                if not entry.is_file():
                    continue
                name = entry.name
                if name.startswith("."):
                    continue
                st = entry.stat()
                size = st.st_size
                prev = self._sizes.get(name)
                growing = prev is not None and size > prev
                partial = name.lower().endswith(PARTIAL_EXTS)
                recent = (now - st.st_mtime) < 8.0
                if partial or growing or (recent and size > 0):
                    seen.add(name)
                    if name not in self.active:
                        self.events.append(("started", name))
                    self.active[name] = Download(name, entry.path, size, st.st_mtime)
                self._sizes[name] = size
            except Exception:
                continue

        # yang hilang dari daftar aktif → selesai
        for name in list(self.active.keys()):
            if name not in seen:
                dl = self.active.pop(name)
                if dl.size > 0:
                    self.events.append(("finished", name))

    def take_events(self) -> list[tuple[str, str]]:
        ev = self.events
        self.events = []
        return ev


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} GB"

# ================================================================= LIRIK
LRC_TIME = re.compile(r"\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]")
_YT_NOISE = re.compile(
    r"\b(official|lyrics?|lyric video|video|audio|visualizer|hd|4k|mv|m/v|"
    r"remaster(ed)?|color coded)\b", re.I)


@dataclass
class LyricsResult:
    synced: bool = False
    lines: list = field(default_factory=list)   # [(waktu_detik, teks), ...]
    status: str = ""                            # "" | "loading" | "notfound" | "error"
    title: str = ""
    artist: str = ""


class LyricsService:
    """Ambil lirik tersinkron dari LRCLIB (gratis, tanpa API key).

    - membersihkan judul YouTube ('(Official Video)', 'ft. ...', '| Label')
    - memilih hasil dengan syncedLyrics + durasi terdekat
    - cache di ~/.cache/notchy/lyrics/
    - fetch di thread; hasil diambil lewat poll()
    """

    API = "https://lrclib.net/api/search"
    UA = "notchy/0.4 (Dynamic Island; Linux/Windows)"

    def __init__(self) -> None:
        self._result: LyricsResult | None = None
        self._busy = False
        self._key = ""
        self._cache_dir = os.path.join(CACHE_DIR, "lyrics")

    # ------------------------------------------------------------ util
    @staticmethod
    def parse_lrc(text: str) -> list[tuple[float, str]]:
        out: list[tuple[float, str]] = []
        for raw in (text or "").splitlines():
            stamps = LRC_TIME.findall(raw)
            if not stamps:
                continue
            content = LRC_TIME.sub("", raw).strip()
            for m, s, frac in stamps:
                t = int(m) * 60 + int(s)
                if frac:
                    t += float("0." + frac)
                out.append((t, content))
        out.sort(key=lambda x: x[0])
        return out

    @staticmethod
    def clean_title(title: str, artist: str) -> tuple[str, str]:
        t = _YT_NOISE.sub(" ", title or "")
        t = re.sub(r"[\(\[].*?[\)\]]", " ", t)
        t = re.split(r"\s+(?:ft\.?|feat\.?)\s+", t, flags=re.I)[0]
        t = t.split("|")[0]
        t = re.sub(r"\s+", " ", t).strip(" -–—")
        a = (artist or "").strip()
        if " - " in t:
            left, right = t.split(" - ", 1)
            left, right = left.strip(), right.strip()
            if left and right:
                return left, right
        return a, t

    def _cache_file(self, key: str) -> str:
        import hashlib

        os.makedirs(self._cache_dir, exist_ok=True)
        return os.path.join(self._cache_dir, hashlib.sha256(key.encode()).hexdigest() + ".json")

    # ------------------------------------------------------------ request
    def request(self, np) -> None:
        if not getattr(np, "available", False) or not np.title:
            return
        artist, track = self.clean_title(np.title, np.artist)
        key = f"{artist.lower()}|{track.lower()}"
        if key == self._key and (self._busy or self._result is not None):
            return
        self._key = key
        self._result = None
        # cache
        try:
            with open(self._cache_file(key), "r", encoding="utf-8") as f:
                d = json.load(f)
            self._result = LyricsResult(
                synced=bool(d.get("synced")), lines=[(float(t), str(s)) for t, s in d.get("lines", [])],
                status="" if d.get("lines") else "notfound", title=track, artist=artist)
            return
        except Exception:
            pass
        self._result = LyricsResult(status="loading", title=track, artist=artist)
        if self._busy:
            return
        self._busy = True
        threading.Thread(target=self._worker, args=(artist, track, float(getattr(np, "length", 0) or 0), key),
                         daemon=True, name="notchy-lyrics").start()

    def _worker(self, artist: str, track: str, duration: float, key: str) -> None:
        try:
            data = None
            for attempt in range(3):
                try:
                    url = (f"{self.API}?track_name={urllib.parse.quote(track)}"
                           f"&artist_name={urllib.parse.quote(artist)}")
                    req = urllib.request.Request(url, headers={"User-Agent": self.UA,
                                                               "Lrclib-Client": self.UA})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        data = json.loads(resp.read(1024 * 1024).decode("utf-8", "replace"))
                    if isinstance(data, list):
                        break
                except Exception:
                    data = None
                time.sleep(1.5 * (attempt + 1))
            if not isinstance(data, list) or not data:
                self._result = LyricsResult(status="notfound", title=track, artist=artist)
                return
            best = None
            best_score = -1.0
            for item in data:
                score = 0.0
                if item.get("syncedLyrics"):
                    score += 2.0
                if duration and item.get("duration"):
                    score += max(0.0, 1.0 - abs(float(item["duration"]) - duration) / 30.0)
                if score > best_score:
                    best_score, best = score, item
            if best is None:
                self._result = LyricsResult(status="notfound", title=track, artist=artist)
                return
            if best.get("syncedLyrics"):
                lines = self.parse_lrc(best["syncedLyrics"])
                result = LyricsResult(synced=True, lines=lines, title=track, artist=artist)
            elif best.get("plainLyrics"):
                lines = [(float(i), ln) for i, ln in enumerate(best["plainLyrics"].splitlines())]
                result = LyricsResult(synced=False, lines=lines, title=track, artist=artist)
            else:
                result = LyricsResult(status="notfound", title=track, artist=artist)
            self._result = result
            if result.lines:
                try:
                    with open(self._cache_file(key), "w", encoding="utf-8") as f:
                        json.dump({"synced": result.synced, "lines": result.lines}, f)
                except Exception:
                    pass
        finally:
            self._busy = False

    def poll(self) -> LyricsResult | None:
        """Sekali-pakai: hasil dikonsumsi supaya UI tidak rebuild tiap tick."""
        res = self._result
        if res is None or res.status == "loading":
            return None
        self._result = None
        return res
