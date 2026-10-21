#!/usr/bin/env python3
"""Convert an Apple UDIF .dmg (koly trailer) to a raw disk image.

Pure stdlib. Input is untrusted: this script only reads the DMG and writes a
raw image to a caller-chosen output path. It never executes DMG content.
"""
import argparse
import plistlib
import struct
import sys
import zlib

SECTOR = 512
CHUNK_ZERO = 0x00000000
CHUNK_RAW = 0x00000001
CHUNK_IGNORE = 0x00000002
CHUNK_ADC = 0x80000004
CHUNK_ZLIB = 0x80000005
CHUNK_BZIP2 = 0x80000006
CHUNK_COMMENT = 0x7FFFFFFE
CHUNK_TERM = 0xFFFFFFFF


def read_koly(data: bytes) -> dict:
    if len(data) < 512:
        raise ValueError("file smaller than koly trailer")
    koly = data[-512:]
    if koly[:4] != b"koly":
        raise ValueError("missing koly trailer")
    xml_offset = struct.unpack(">Q", koly[0xD8:0xE0])[0]
    xml_length = struct.unpack(">Q", koly[0xE0:0xE8])[0]
    data_fork_offset = struct.unpack(">Q", koly[0x18:0x20])[0]
    data_fork_length = struct.unpack(">Q", koly[0x20:0x28])[0]
    return {
        "xml_offset": xml_offset,
        "xml_length": xml_length,
        "data_fork_offset": data_fork_offset,
        "data_fork_length": data_fork_length,
    }


def parse_blkx(blob: bytes) -> dict:
    if blob[:4] != b"mish":
        raise ValueError("blkx missing mish signature")
    sector_number = struct.unpack(">Q", blob[0x08:0x10])[0]
    sector_count = struct.unpack(">Q", blob[0x10:0x18])[0]
    data_offset = struct.unpack(">Q", blob[0x18:0x20])[0]
    blocks_count = struct.unpack(">I", blob[0xC8:0xCC])[0]
    entries = []
    off = 0xCC
    for _ in range(blocks_count):
        chunk_type = struct.unpack(">I", blob[off : off + 4])[0]
        sector_off = struct.unpack(">Q", blob[off + 8 : off + 16])[0]
        sector_cnt = struct.unpack(">Q", blob[off + 16 : off + 24])[0]
        comp_off = struct.unpack(">Q", blob[off + 24 : off + 32])[0]
        comp_len = struct.unpack(">Q", blob[off + 32 : off + 40])[0]
        entries.append((chunk_type, sector_off, sector_cnt, comp_off, comp_len))
        off += 40
    return {
        "sector_number": sector_number,
        "sector_count": sector_count,
        "data_offset": data_offset,
        "entries": entries,
    }


def decompress_chunk(chunk_type: int, payload: bytes) -> bytes:
    if chunk_type == CHUNK_ZERO:
        return b"\x00" * (len(payload) if payload else 0)
    if chunk_type == CHUNK_RAW:
        return payload
    if chunk_type == CHUNK_ZLIB:
        return zlib.decompress(payload)
    if chunk_type == CHUNK_ADC:
        return adc_decompress(payload)
    if chunk_type == CHUNK_IGNORE:
        return b""
    if chunk_type in (CHUNK_COMMENT, CHUNK_TERM):
        return b""
    raise ValueError(f"unsupported chunk type 0x{chunk_type:08x}")


def adc_decompress(src: bytes) -> bytes:
    """Apple Data Compression (ADC) — enough of the format for DMG blkx."""
    out = bytearray()
    i = 0
    n = len(src)
    while i < n:
        cmd = src[i]
        i += 1
        if cmd & 0x80:
            length = (cmd >> 4) + 3  # 3..18? spec: ((cmd >> 4) & 0x7) + 3
            length = ((cmd >> 4) & 0x7) + 3
            if i >= n:
                break
            offset = ((cmd & 0x0F) << 8) | src[i]
            i += 1
            if offset == 0:
                raise ValueError("adc zero offset")
            for _ in range(length):
                out.append(out[-offset])
        else:
            length = (cmd & 0x7F) + 1
            out.extend(src[i : i + length])
            i += length
    return bytes(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dmg")
    ap.add_argument("out_img")
    args = ap.parse_args()

    data = open(args.dmg, "rb").read()
    meta = read_koly(data)
    xml = data[meta["xml_offset"] : meta["xml_offset"] + meta["xml_length"]]
    plist = plistlib.loads(xml)
    rfork = plist.get("resource-fork") or {}
    blkx_list = rfork.get("blkx") or []
    if not blkx_list:
        print("no blkx entries", file=sys.stderr)
        return 1

    regions = []
    for item in blkx_list:
        blob = item.get("Data") or b""
        regions.append(parse_blkx(blob))

    # figure out total size of the reconstructed image
    end = 0
    for r in regions:
        end = max(end, (r["sector_number"] + r["sector_count"]) * SECTOR)
    print(f"image size: {end} bytes, regions: {len(regions)}", file=sys.stderr)

    out = bytearray(end)
    dfork = data[meta["data_fork_offset"] : meta["data_fork_offset"] + meta["data_fork_length"]]

    for r in regions:
        base = r["sector_number"] * SECTOR
        for chunk_type, sector_off, sector_cnt, comp_off, comp_len in r["entries"]:
            if chunk_type in (CHUNK_COMMENT, CHUNK_TERM, CHUNK_IGNORE):
                continue
            dest = base + sector_off * SECTOR
            length = sector_cnt * SECTOR
            if chunk_type == CHUNK_ZERO:
                # already zero-filled
                continue
            payload = dfork[comp_off : comp_off + comp_len]
            piece = decompress_chunk(chunk_type, payload)
            if len(piece) < length:
                piece = piece + b"\x00" * (length - len(piece))
            out[dest : dest + length] = piece[:length]

    with open(args.out_img, "wb") as f:
        f.write(out)
    print(f"wrote {args.out_img}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
