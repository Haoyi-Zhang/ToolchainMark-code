from __future__ import annotations

from .evidence_boundary import first_valid_candidate
import hashlib
import re
import struct
import subprocess
from pathlib import Path

from .model import ExtractionError

MAGIC = b'WMR2'
VERSION = 1
SENTINEL_TAG = b'\x00' * 8
SYMBOL_RE = re.compile(
    r'^wmrec_([0-9a-f]{16})_([0-9a-f]{4})_([0-9a-f]{4})_([0-9a-f]{4})_([0-9a-f]{2,8})_([0-9a-f]{16})$'
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def key_tag(key: str) -> bytes:
    return hashlib.sha256(key.encode('utf-8')).digest()[:8]


def checksum(payload: bytes) -> bytes:
    return hashlib.sha256(payload).digest()[:8]


def xor_stream(data: bytes, key: str) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < len(data):
        out.extend(hashlib.sha256(key.encode('utf-8') + counter.to_bytes(4, 'big')).digest())
        counter += 1
    return bytes(a ^ b for a, b in zip(data, out))


def make_record(payload: bytes, key: str, key_ignored: bool = False) -> bytes:
    if len(payload) > 65535:
        raise ValueError('payload too long')
    tag = SENTINEL_TAG if key_ignored else key_tag(key)
    encoded = payload if key_ignored else xor_stream(payload, key)
    return MAGIC + bytes([VERSION]) + tag + struct.pack('>H', len(payload)) + encoded + checksum(payload)


def _candidate_locate_record(data: bytes) -> tuple[int, int]:
    start = data.find(MAGIC)
    if start < 0:
        raise ExtractionError('absent', 'logical record magic not found')
    header = start + 4 + 1 + 8 + 2
    if header > len(data):
        raise ExtractionError('malformed', 'truncated logical record header')
    length = struct.unpack('>H', data[start + 13:start + 15])[0]
    end = header + length + 8
    if end > len(data):
        raise ExtractionError('malformed', 'truncated logical record body')
    return start, end


def parse_record(data: bytes, key: str, key_ignored: bool = False, checksum_bypass: bool = False) -> bytes:
    start, end = locate_record(data)
    version = data[start + 4]
    if version != VERSION:
        raise ExtractionError('version', f'unsupported version {version}')
    tag = data[start + 5:start + 13]
    length = struct.unpack('>H', data[start + 13:start + 15])[0]
    encoded = data[start + 15:start + 15 + length]
    recorded_checksum = data[start + 15 + length:end]
    if key_ignored:
        payload = encoded
    else:
        if tag != key_tag(key):
            raise ExtractionError('wrong-key', 'key tag mismatch')
        payload = xor_stream(encoded, key)
    if not checksum_bypass and recorded_checksum != checksum(payload):
        raise ExtractionError('checksum', 'payload checksum mismatch')
    return payload


def symbol_names(payload: bytes, key: str, key_ignored: bool = False) -> list[str]:
    tag = SENTINEL_TAG if key_ignored else key_tag(key)
    chunks = [payload[i:i + 4] for i in range(0, len(payload), 4)] or [b'']
    total = len(chunks)
    digest = checksum(payload).hex()
    return [
        f'wmrec_{tag.hex()}_{len(payload):04x}_{i:04x}_{total:04x}_{chunk.hex() or "00"}_{digest}'
        for i, chunk in enumerate(chunks)
    ]


def parse_symbols(binary: Path, key: str, key_ignored: bool = False, checksum_bypass: bool = False) -> bytes:
    proc = subprocess.run(['nm', '-g', str(binary)], text=True, capture_output=True, timeout=5)
    if proc.returncode != 0:
        raise ExtractionError('tool', f'nm failed: {proc.stderr.strip()}')
    rows: list[tuple[bytes, int, int, int, bytes, bytes]] = []
    for line in proc.stdout.splitlines():
        name = line.split()[-1] if line.split() else ''
        match = SYMBOL_RE.match(name)
        if match:
            tag_hex, length_hex, idx_hex, total_hex, chunk_hex, checksum_hex = match.groups()
            rows.append((bytes.fromhex(tag_hex), int(length_hex, 16), int(idx_hex, 16), int(total_hex, 16), bytes.fromhex(chunk_hex), bytes.fromhex(checksum_hex)))
    if not rows:
        raise ExtractionError('absent', 'watermark symbols not found')
    tags = {r[0] for r in rows}
    lengths = {r[1] for r in rows}
    totals = {r[3] for r in rows}
    checksums = {r[5] for r in rows}
    if len(tags) != 1 or len(lengths) != 1 or len(totals) != 1 or len(checksums) != 1:
        raise ExtractionError('malformed', 'inconsistent watermark symbol set')
    total = next(iter(totals))
    if len(rows) != total or {r[2] for r in rows} != set(range(total)):
        raise ExtractionError('malformed', 'incomplete watermark symbol set')
    tag = next(iter(tags))
    if not key_ignored and tag != key_tag(key):
        raise ExtractionError('wrong-key', 'symbol key tag mismatch')
    length = next(iter(lengths))
    payload = b''.join(r[4] for r in sorted(rows, key=lambda r: r[2]))[:length]
    recorded_checksum = next(iter(checksums))
    if not checksum_bypass and recorded_checksum != checksum(payload):
        raise ExtractionError('checksum', 'symbol payload checksum mismatch')
    return payload


def locate_record(data):
    def _parse(candidate_blob):
        return _candidate_locate_record(candidate_blob)
    def _absent():
        return _candidate_locate_record(data)
    return first_valid_candidate(data, MAGIC, _parse, _absent)
