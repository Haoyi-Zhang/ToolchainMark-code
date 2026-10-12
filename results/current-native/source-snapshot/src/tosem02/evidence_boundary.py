from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import hashlib
import os
import re
import subprocess
import tempfile
from typing import Any, Callable

from .model import ExtractionError


class ToolObservationError(RuntimeError):
    """The observation tool failed; absence must not be inferred."""


class ObservationUnavailable(RuntimeError):
    """A required execution or output observation was not produced."""


@dataclass(frozen=True)
class Candidate:
    """An accepted candidate, including a possibly empty value and its bounds.

    A parser returns bounds relative to its candidate slice. The public scanner
    returns bounds relative to the original buffer. Acceptance is explicit,
    never inferred from payload truthiness or a nonzero starting offset.
    """
    start: int
    end: int
    value: Any


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
        match=re.search(r'\[\s*\d+\]\s+([^\s]+)', line)
        if match:
            names.add(match.group(1))
    return names


def observe_elf_section(
    artifact: str | os.PathLike[str] | Path,
    section_name: str,
    *,
    objcopy: str='objcopy',
    readelf: str='readelf',
    run: Callable[..., subprocess.CompletedProcess[str]] | None=None,
) -> SectionObservation:
    """Observe an ELF section without conflating tool failure with absence.

    Absence is established from a successful section-table read. Once the
    section is known to exist, a non-zero dump command or a missing dump file
    is a tool failure and must make the enclosing relation inadmissible.
    """
    artifact_path=Path(artifact)
    run = subprocess.run if run is None else run
    def invoke(command):
        try:
            return run(command, text=True, capture_output=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ToolObservationError('section observation unavailable: ' + type(exc).__name__) from exc
    listing=(readelf, '-W', '-S', str(artifact_path))
    listed=invoke(listing)
    if listed.returncode != 0:
        raise ToolObservationError(
            f'readelf failed with {listed.returncode}: {listed.stderr.strip()}'
        )
    names = _section_names(listed.stdout)
    if not names and 'There are no sections in this file' not in listed.stdout:
        raise ToolObservationError('readelf reported success without a readable section table')
    if section_name not in names:
        return SectionObservation('ABSENT', None, tuple(listing), 0, listed.stderr, False)
    with tempfile.TemporaryDirectory(prefix='tosem02-section-') as tmp:
        dump=Path(tmp)/'section.bin'
        command=(objcopy, '--dump-section', f'{section_name}={dump}', str(artifact_path))
        completed=invoke(command)
        if completed.returncode != 0:
            raise ToolObservationError(
                f'objcopy failed with {completed.returncode}: {completed.stderr.strip()}'
            )
        if not dump.is_file():
            raise ToolObservationError('objcopy reported success but produced no dump file')
        try:
            data = dump.read_bytes()
        except OSError as exc:
            raise ToolObservationError('section dump unreadable') from exc
        return SectionObservation('PRESENT', data, tuple(command), 0, completed.stderr, True)


def first_valid_candidate(
    blob: bytes,
    magic: bytes,
    parse_candidate: Callable[[bytes], Candidate | None],
    absent_factory: Callable[[], Any],
) -> Any:
    """Scan once in byte order, returning the first explicitly accepted record.

    If none is accepted, preserve the most informative typed rejection:
    checksum > wrong-key > version > malformed. Ties keep the earliest error.
    Absence is reserved for no magic (or callbacks that reject without a type).
    Tool/I/O failures and unexpected parser exceptions are not domain absence.
    """
    if not magic:
        raise ValueError('candidate magic must not be empty')
    priorities = {'malformed': 1, 'version': 2, 'wrong-key': 3, 'checksum': 4}
    rejection = None
    start=0
    while True:
        offset=blob.find(magic, start)
        if offset < 0:
            if rejection is not None:
                raise rejection
            return absent_factory()
        try:
            candidate=parse_candidate(blob[offset:])
        except ExtractionError as exc:
            if exc.kind not in priorities:
                raise
            if rejection is None or priorities[exc.kind] > priorities[rejection.kind]:
                rejection = exc
            candidate=None
        if candidate is not None:
            if not isinstance(candidate, Candidate):
                raise TypeError('parser must return Candidate or None')
            if candidate.start != 0 or not 0 < candidate.end <= len(blob) - offset:
                raise ValueError('invalid candidate-relative bounds')
            return replace(candidate, start=offset, end=offset + candidate.end)
        start=offset + 1


def require_observed_output(*, returncode: int | None, path: Path | None, stdout: str='') -> str:
    if returncode != 0:
        raise ObservationUnavailable(f'program did not terminate successfully: {returncode}')
    if path is None:
        return stdout
    if not path.is_file():
        raise ObservationUnavailable(f'required output file was not produced: {path.name}')
    try:
        return path.read_text(encoding='utf-8')
    except (OSError, UnicodeError) as exc:
        raise ObservationUnavailable('required output file is unreadable') from exc
