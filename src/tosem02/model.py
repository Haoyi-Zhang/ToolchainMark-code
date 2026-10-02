from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


class ExtractionError(RuntimeError):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


@dataclass(frozen=True)
class BuildRequest:
    host: Path
    payload: bytes
    key: str
    compiler: str
    optimization: str
    work_dir: Path
    marked: bool = True
    guard_upstream: bool = False


@dataclass
class BuildResult:
    binary: Path
    source: Path
    requested_compiler: str
    actual_compiler: str
    requested_optimization: str
    actual_optimization: str
    carrier: str
    mutant_id: str
    command: list[str]
    source_sha256: str
    binary_sha256: str
    return_code: int
    stderr: str
    requested_payload_hex: str
    effective_payload_hex: str
    key: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data['binary'] = str(self.binary)
        data['source'] = str(self.source)
        return data


@dataclass
class RelationOutcome:
    passed: bool
    detail: str
    observations: dict[str, Any]
