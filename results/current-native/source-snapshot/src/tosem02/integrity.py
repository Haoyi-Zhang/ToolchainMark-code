"""Seed-free, representation-scoped evidence for checksum-only interventions.

Snapshots are taken before the transformation, not reconstructed from its
output. Checksum-bypassed decoding observes the retained payload only; the
strict carrier observer must separately establish a checksum rejection.
This code shares the record/parser family and is not an independent decoder.
"""
from dataclasses import dataclass
from pathlib import Path
import subprocess

from .evidence_boundary import ToolObservationError, observe_elf_section
from .model import ExtractionError
from .record import SYMBOL_RE, locate_record, parse_record, parse_symbols


@dataclass(frozen=True)
class IntegrityMaterial:
    protected: tuple
    checksums: tuple[bytes, ...]
    payload: bytes


def checksum_material(carrier: str, binary: Path, key: str,
                      source: IntegrityMaterial | None = None) -> IntegrityMaterial:
    """Capture all non-checksum material in the declared carrier boundary.

    For strings the boundary is the whole byte buffer. For sections it is the
    whole designated section, not unrelated ELF layout. For symbols it is the
    complete indexed wmrec name set, not symbol addresses or unrelated names.
    """
    if carrier == 'symbol':
        proc = subprocess.run(['nm', '-g', str(binary)], text=True,
                              capture_output=True, timeout=20)
        if proc.returncode != 0:
            raise ToolObservationError('symbol intervention observation failed')
        rows = []
        for line in proc.stdout.splitlines():
            name = line.split()[-1] if line.split() else ''
            if not name.startswith('wmrec_'):
                continue
            match = SYMBOL_RE.fullmatch(name)
            if match is None:
                raise ExtractionError('malformed', 'invalid carrier symbol name')
            fields = match.groups()
            rows.append((fields[:-1], bytes.fromhex(fields[-1])))
        # Order in nm output is not carrier identity; chunk indices are.
        rows.sort()
        payload = parse_symbols(binary, key, checksum_bypass=source is not None)
        return IntegrityMaterial(tuple(row[0] for row in rows),
                                 tuple(row[1] for row in rows), payload)
    if carrier == 'string':
        data = binary.read_bytes()
    elif carrier == 'section':
        observed = observe_elf_section(binary, '.wmrec')
        if observed.status != 'PRESENT' or observed.data is None:
            raise ToolObservationError('section intervention material unavailable')
        data = observed.data
    else:
        raise ValueError('unknown carrier')
    # Bind the follow-up to the exact source-accepted record. A fresh bypassed
    # scan could select an earlier bad-checksum candidate instead of that record.
    start, end = locate_record(data, key) if source is None else source.protected[:2]
    if not 0 <= start < end <= len(data):
        raise ExtractionError('malformed', 'source record bounds not retained')
    payload = parse_record(data[start:end], key, checksum_bypass=source is not None)
    protected = (start, end, len(data), data[:end - 8], data[end:])
    return IntegrityMaterial(protected, (data[end - 8:end],), payload)


def intervention_facts(source: IntegrityMaterial, followup: IntegrityMaterial) -> dict[str, bool]:
    return {
        'nonintervened_payload_preserved': source.payload == followup.payload,
        'checksum_material_changed': source.checksums != followup.checksums,
        'nonchecksum_material_preserved': source.protected == followup.protected,
    }
