from __future__ import annotations

from .evidence_boundary import first_valid_candidate
from .evidence_boundary import ToolObservationError, observe_elf_section
from dataclasses import dataclass
from pathlib import Path
import hashlib
import os
import re
import subprocess
import tempfile
from typing import Any, Callable


class ToolObservationError(RuntimeError):
    """The observation tool failed; absence must not be inferred."""


class ObservationUnavailable(RuntimeError):
    """A required execution or output observation was not produced."""


@dataclass(frozen=True)
class SectionObservation:
    status: str  # PRESENT, ABSENT, TOOL_FAILURE
    data: bytes | None
    command: tuple[str, ...]
    returncode: int
    stderr: str
    dump_created: bool


def file_sha256(path: str | os.PathLike[str] | Path) -> str | None:
    p=Path(path)
    if not p.is_file():
        return None
    h=hashlib.sha256()
    with p.open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def _section_names(readelf_stdout: str) -> set[str]:
    names=set()
    for line in readelf_stdout.splitlines():
        # Handles both '[ 1] .text ...' and '[12] .wm_record ...'.
        match=re.search(r'\]\s+([^\s]+)', line)
        if match:
            names.add(match.group(1))
    return names


def observe_elf_section(
    artifact: str | os.PathLike[str] | Path,
    section_name: str,
    *,
    objcopy: str='objcopy',
    readelf: str='readelf',
    run: Callable[..., subprocess.CompletedProcess[str]]=subprocess.run,
) -> SectionObservation:
    """Observe an ELF section without conflating tool failure with absence.

    Absence is established from a successful section-table read. Once the
    section is known to exist, a non-zero dump command or a missing dump file
    is a tool failure and must make the enclosing relation inadmissible.
    """
    artifact_path=Path(artifact)
    listing=(readelf, '-W', '-S', str(artifact_path))
    listed=run(listing, text=True, capture_output=True)
    if listed.returncode != 0:
        raise ToolObservationError(
            f'readelf failed with {listed.returncode}: {listed.stderr.strip()}'
        )
    if section_name not in _section_names(listed.stdout):
        return SectionObservation('ABSENT', None, tuple(listing), 0, listed.stderr, False)
    with tempfile.TemporaryDirectory(prefix='tosem02-section-') as tmp:
        dump=Path(tmp)/'section.bin'
        command=(objcopy, '--dump-section', f'{section_name}={dump}', str(artifact_path))
        completed=run(command, text=True, capture_output=True)
        if completed.returncode != 0:
            raise ToolObservationError(
                f'objcopy failed with {completed.returncode}: {completed.stderr.strip()}'
            )
        if not dump.is_file():
            raise ToolObservationError('objcopy reported success but produced no dump file')
        return SectionObservation('PRESENT', dump.read_bytes(), tuple(command), 0, completed.stderr, True)


def result_is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (bytes, bytearray, memoryview)):
        return len(value) > 0
    if isinstance(value, tuple):
        return bool(value) and result_is_present(value[0])
    for attr in ('payload', 'value', 'data'):
        if hasattr(value, attr):
            return getattr(value, attr) is not None
    for attr in ('present', 'ok', 'valid', 'success'):
        if hasattr(value, attr):
            return bool(getattr(value, attr))
    status=getattr(value, 'status', None)
    if status is not None:
        return str(status).lower() in {'present','ok','valid','success','satisfied'}
    return bool(value)


def _candidate_first_valid_candidate(
    blob: bytes,
    magic: bytes,
    parse_candidate: Callable[[bytes], Any],
    absent_factory: Callable[[], Any],
) -> Any:
    """Return the first valid record, not merely the first magic occurrence."""
    start=0
    while True:
        offset=blob.find(magic, start)
        if offset < 0:
            return absent_factory()
        try:
            candidate=parse_candidate(blob[offset:])
        except (ValueError, IndexError, UnicodeError):
            candidate=None
        if result_is_present(candidate):
            return candidate
        start=offset + 1


def require_observed_output(*, returncode: int | None, path: Path | None, stdout: str='') -> str:
    if returncode != 0:
        raise ObservationUnavailable(f'program did not terminate successfully: {returncode}')
    if path is None:
        return stdout
    if not path.is_file():
        raise ObservationUnavailable(f'required output file was not produced: {path.name}')
    return path.read_text(encoding='utf-8')


def first_valid_candidate(blob, magic, parse_candidate, absent_factory):
    def _parse(candidate_blob):
        return _candidate_first_valid_candidate(candidate_blob, magic, parse_candidate, absent_factory)
    def _absent():
        return _candidate_first_valid_candidate(blob, magic, parse_candidate, absent_factory)
    return first_valid_candidate(blob, magic, _parse, _absent)
