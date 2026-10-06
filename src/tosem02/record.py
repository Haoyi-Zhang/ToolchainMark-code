from __future__ import annotations

from .evidence_boundary import Candidate, first_valid_candidate
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


def _parse_candidate(data: bytes, key: str | None = None, *, key_ignored: bool = False,
                     checksum_bypass: bool = False) -> Candidate:
    """Validate only the candidate at slice offset zero; never rescan a slice."""
    header = 4 + 1 + 8 + 2
    if header > len(data):
        raise ExtractionError('malformed', 'truncated logical record header')
    version = data[4]
    if version != VERSION:
        raise ExtractionError('version', f'unsupported version {version}')
    length = struct.unpack('>H', data[13:15])[0]
    end = header + length + 8
    if end > len(data):
        raise ExtractionError('malformed', 'truncated logical record body')
    if key is None:
        return Candidate(0, end, None)
    tag = data[5:13]
    encoded = data[15:15 + length]
    recorded_checksum = data[15 + length:end]
    if key_ignored:
        payload = encoded
    else:
        if tag != key_tag(key):
            raise ExtractionError('wrong-key', 'key tag mismatch')
        payload = xor_stream(encoded, key)
    if not checksum_bypass and recorded_checksum != checksum(payload):
        raise ExtractionError('checksum', 'payload checksum mismatch')
    return Candidate(0, end, payload)


def _absent_record():
    raise ExtractionError('absent', 'logical record magic not found')


def parse_record(data: bytes, key: str, key_ignored: bool = False, checksum_bypass: bool = False) -> bytes:
    accepted = first_valid_candidate(
        data, MAGIC,
        lambda blob: _parse_candidate(blob, key, key_ignored=key_ignored, checksum_bypass=checksum_bypass),
        _absent_record,
    )
    return accepted.value


def symbol_names(payload: bytes, key: str, key_ignored: bool = False) -> list[str]:
    if len(payload) > 65535:
        raise ValueError('payload too long')
    tag = SENTINEL_TAG if key_ignored else key_tag(key)
    chunks = [payload[i:i + 4] for i in range(0, len(payload), 4)] or [b'']
    total = len(chunks)
    digest = checksum(payload).hex()
    return [
        f'wmrec_{tag.hex()}_{len(payload):04x}_{i:04x}_{total:04x}_{chunk.hex() or "00"}_{digest}'
        for i, chunk in enumerate(chunks)
    ]


def parse_symbols(binary: Path, key: str, key_ignored: bool = False, checksum_bypass: bool = False) -> bytes:
    proc = subprocess.run(['nm', '-g', str(binary)], text=True, capture_output=True, timeout=20)
    if proc.returncode != 0:
        raise ExtractionError('tool', f'nm failed: {proc.stderr.strip()}')
    rows: list[tuple[bytes, int, int, int, bytes, bytes]] = []
    for line in proc.stdout.splitlines():
        name = line.split()[-1] if line.split() else ''
        match = SYMBOL_RE.match(name)
        if match:
            tag_hex, length_hex, idx_hex, total_hex, chunk_hex, checksum_hex = match.groups()
            if len(chunk_hex) % 2:
                raise ExtractionError('malformed', 'symbol chunk is not a whole number of bytes')
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
    length = next(iter(lengths))
    if total != max(1, (length + 3) // 4):
        raise ExtractionError('malformed', 'symbol count does not match declared payload length')
    ordered = sorted(rows, key=lambda r: r[2])
    if length == 0:
        if ordered[0][4] != b'\x00':
            raise ExtractionError('malformed', 'invalid empty-payload placeholder')
        payload = b''
    else:
        for index, row in enumerate(ordered):
            if len(row[4]) != min(4, length - 4 * index):
                raise ExtractionError('malformed', 'symbol chunk width does not match declared payload length')
        payload = b''.join(row[4] for row in ordered)
    tag = next(iter(tags))
    if not key_ignored and tag != key_tag(key):
        raise ExtractionError('wrong-key', 'symbol key tag mismatch')
    recorded_checksum = next(iter(checksums))
    if not checksum_bypass and recorded_checksum != checksum(payload):
        raise ExtractionError('checksum', 'symbol payload checksum mismatch')
    return payload


def locate_record(data: bytes, key: str | None = None, *, key_ignored: bool = False) -> tuple[int, int]:
    """Return absolute bounds; with a key, require full record acceptance.

    Without a key this is a structural locator (version and bounds only), not
    an extraction or integrity decision.
    """
    accepted = first_valid_candidate(
        data, MAGIC, lambda blob: _parse_candidate(blob, key, key_ignored=key_ignored), _absent_record,
    )
    return accepted.start, accepted.end
