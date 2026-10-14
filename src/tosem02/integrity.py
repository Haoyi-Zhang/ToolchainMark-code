"""Seed-free, representation-scoped evidence for checksum-only interventions.

Snapshots are taken before the transformation, not reconstructed from its
output. Checksum-bypassed decoding observes the retained payload only; the
strict carrier observer must separately establish a checksum rejection.
This code shares the record/parser family and is not an independent decoder.
"""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import subprocess
import tempfile

from .evidence_boundary import ToolObservationError, observe_elf_section
from .model import ExtractionError
from .record import SYMBOL_RE, locate_record, parse_record, parse_symbol_names


@dataclass(frozen=True)
class IntegrityMaterial:
    protected: tuple
    checksums: tuple[bytes, ...]
    payload: bytes


@dataclass(frozen=True)
class IntegritySnapshot:
    material: IntegrityMaterial
    strict: dict[str, str]
    artifact_bytes: bytes

    def identity(self) -> dict:
        return {'sha256': hashlib.sha256(self.artifact_bytes).hexdigest(),
                'bytes': len(self.artifact_bytes)}


def _carrier_view(carrier: str, binary: Path):
    if carrier == 'symbol':
        proc = subprocess.run(['nm', '-g', str(binary)], text=True,
                              capture_output=True, timeout=20)
        if proc.returncode != 0:
            raise ToolObservationError('symbol intervention observation failed')
        return [line.split()[-1] for line in proc.stdout.splitlines() if line.split()]
    if carrier == 'string':
        return binary.read_bytes()
    if carrier == 'section':
        observed = observe_elf_section(binary, '.wmrec')
        if observed.status != 'PRESENT' or observed.data is None:
            raise ToolObservationError('section intervention material unavailable')
        return observed.data
    raise ValueError('unknown carrier')


def _material_from_view(carrier: str, view, key: str,
                        source: IntegrityMaterial | None = None) -> IntegrityMaterial:
    """Capture all non-checksum material in the declared carrier boundary.

    For strings the boundary is the whole byte buffer. For sections it is the
    whole designated section, not unrelated ELF layout. For symbols it is the
    complete indexed wmrec name set, not symbol addresses or unrelated names.
    """
    if carrier == 'symbol':
        rows = []
        for name in view:
            if not name.startswith('wmrec_'):
                continue
            match = SYMBOL_RE.fullmatch(name)
            if match is None:
                raise ExtractionError('malformed', 'invalid carrier symbol name')
            fields = match.groups()
            rows.append((fields[:-1], bytes.fromhex(fields[-1])))
        # Order in nm output is not carrier identity; chunk indices are.
        rows.sort()
        payload = parse_symbol_names(view, key, checksum_bypass=source is not None)
        return IntegrityMaterial(tuple(row[0] for row in rows),
                                 tuple(row[1] for row in rows), payload)
    data = view
    # Bind the follow-up to the exact source-accepted record. A fresh bypassed
    # scan could select an earlier bad-checksum candidate instead of that record.
    start, end = locate_record(data, key) if source is None else source.protected[:2]
    if not 0 <= start < end <= len(data):
        raise ExtractionError('malformed', 'source record bounds not retained')
    payload = parse_record(data[start:end], key, checksum_bypass=source is not None)
    protected = (start, end, len(data), data[:end - 8], data[end:])
    return IntegrityMaterial(protected, (data[end - 8:end],), payload)


def checksum_material(carrier: str, binary: Path, key: str,
                      source: IntegrityMaterial | None = None) -> IntegrityMaterial:
    """Compatibility material observation, using one utility view for symbols."""
    return _material_from_view(carrier, _carrier_view(carrier, binary), key, source)


def checksum_snapshot(carrier: str, binary: Path, key: str,
                      source: IntegrityMaterial | None = None) -> IntegritySnapshot:
    """Capture strict rejection and locality from one immutable owned view.

    Byte capture is the boundary. For ELF utilities a private copy supplies
    that exact captured artifact, not a second live-path read. Tool fidelity
    and private-copy isolation remain assumptions; this is not an adversarial
    filesystem/ABA defense, parser independence or cryptographic assurance.
    """
    raw = binary.read_bytes()
    if carrier == 'string':
        view = raw
    else:
        with tempfile.TemporaryDirectory(prefix='tosem02-integrity-') as tmp:
            captured = Path(tmp) / binary.name
            captured.write_bytes(raw)
            view = _carrier_view(carrier, captured)
            if captured.read_bytes() != raw:
                raise ToolObservationError('observer modified its private artifact')
    decoder = parse_symbol_names if carrier == 'symbol' else parse_record
    try:
        strict = {'kind': 'payload', 'value': decoder(view, key).hex()}
    except ExtractionError as exc:
        if exc.kind not in {'absent', 'wrong-key', 'checksum', 'malformed', 'version'}:
            raise
        strict = {'kind': 'rejection', 'value': exc.kind}
    material = _material_from_view(carrier, view, key, source)
    return IntegritySnapshot(material, strict, raw)


def intervention_facts(source: IntegrityMaterial, followup: IntegrityMaterial) -> dict[str, bool]:
    return {
        'nonintervened_payload_preserved': source.payload == followup.payload,
        'checksum_material_changed': source.checksums != followup.checksums,
        'nonchecksum_material_preserved': source.protected == followup.protected,
    }
