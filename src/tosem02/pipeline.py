from __future__ import annotations

from .evidence_boundary import first_valid_candidate
from .evidence_boundary import ToolObservationError, observe_elf_section
import json
import os
import shutil
import subprocess
import threading
from pathlib import Path

from .model import BuildRequest, BuildResult, ExtractionError
from .record import MAGIC, checksum, key_tag, locate_record, make_record, parse_record, parse_symbols, sha256_bytes, symbol_names

UPSTREAM_GUARDED = {'M01', 'M02', 'M03', 'M04', 'M05', 'M12'}


def _host_compile_flags(host: Path) -> tuple[list[str], list[str]]:
    """Return frozen compile and link flags for the six library-backed subjects."""
    name = host.name
    mapping: dict[str, tuple[list[str], list[str]]] = {
        'H13-zlib.c': ([], ['-lz']),
        'H14-openssl.c': (['-Wno-deprecated-declarations'], ['-lcrypto']),
        'H15-sqlite.c': ([], ['-lsqlite3']),
        'H16-xml.c': (['-I/usr/include/libxml2'], ['-lxml2']),
        'H17-json.c': ([], ['-ljson-c']),
        'H18-png.c': ([], ['-lpng']),
    }
    return mapping.get(name, ([], []))


class Pipeline:
    def __init__(self, carrier: str, mutant_id: str = 'CLEAN', pilot: bool = False):
        if carrier not in {'string', 'symbol', 'section'}:
            raise ValueError(f'unknown carrier {carrier}')
        self.carrier = carrier
        self.mutant_id = mutant_id
        self.pilot = pilot
        self.build_counter = 0
        self.first_marked_result: BuildResult | None = None
        self.latest_payload: bytes | None = None
        self.latest_key: str | None = None
        self.original_paths: set[Path] = set()
        self._state_lock = threading.RLock()
        self._overlap_barrier: threading.Barrier | None = None
        self._overlap_payloads: dict[str, bytes] = {}
        self._request_counts: dict[tuple[str, bytes, str, str, str, bool], int] = {}
        self._last_extracted_binary: Path | None = None
        self._last_extracted_payload: bytes | None = None
        self._extracted_binaries: set[Path] = set()

    @property
    def active_mutant(self) -> str:
        return self.mutant_id

    def begin_overlapping_builds(self, parties: int = 2) -> None:
        """Freeze a controlled staging rendezvous for an overlap-sensitive relation."""
        with self._state_lock:
            if self._overlap_barrier is not None:
                raise RuntimeError('overlap rendezvous already active')
            self._overlap_payloads = {}
            self._overlap_barrier = threading.Barrier(parties)

    def end_overlapping_builds(self) -> None:
        with self._state_lock:
            self._overlap_barrier = None
            self._overlap_payloads = {}

    @staticmethod
    def _corrupt_payload(payload: bytes) -> bytes:
        if not payload:
            return b'\x01'
        return bytes([payload[0] ^ 1]) + payload[1:]

    def _mutant_enabled(self, request: BuildRequest, mutant: str) -> bool:
        if self.mutant_id != mutant:
            return False
        if request.guard_upstream and mutant in UPSTREAM_GUARDED:
            return False
        return True

    @staticmethod
    def _copy_context(source: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    def build(self, request: BuildRequest) -> BuildResult:
        request.work_dir.mkdir(parents=True, exist_ok=True)
        with self._state_lock:
            overlap_active = self._overlap_barrier is not None
            first_marked_result = self.first_marked_result
        if (request.marked and self._mutant_enabled(request, 'M18') and not overlap_active
                and first_marked_result is not None):
            return first_marked_result

        with self._state_lock:
            self.build_counter += 1
            build_number = self.build_counter
            signature = (request.host.name, request.payload, request.key, request.compiler, request.optimization, request.marked)
            self._request_counts[signature] = self._request_counts.get(signature, 0) + 1
            signature_count = self._request_counts[signature]
            overlap_barrier = self._overlap_barrier
        build_dir = request.work_dir / f'build-{build_number:02d}'
        build_dir.mkdir(parents=True, exist_ok=True)
        source_path = build_dir / 'host.c'
        binary_path = build_dir / 'artifact.bin'

        requested_payload = request.payload
        effective_payload = requested_payload
        if request.marked and overlap_barrier is not None:
            overlap_key = str(request.work_dir)
            with self._state_lock:
                self._overlap_payloads[overlap_key] = requested_payload
            overlap_barrier.wait(timeout=20)
            if self.mutant_id == 'M20':
                with self._state_lock:
                    # The shared staging slot deterministically retains the lexicographically latest request.
                    winner_key = sorted(self._overlap_payloads)[-1]
                    effective_payload = self._overlap_payloads[winner_key]
        include_carrier = request.marked
        if request.marked:
            if self._mutant_enabled(request, 'M01'):
                include_carrier = False
            elif self._mutant_enabled(request, 'M02'):
                effective_payload = effective_payload[:-1]
            elif self._mutant_enabled(request, 'M03') and effective_payload:
                effective_payload = bytes([effective_payload[0] ^ 1]) + effective_payload[1:]
            elif self._mutant_enabled(request, 'M04'):
                effective_payload = b'fixed-payload'
            elif self._mutant_enabled(request, 'M05'):
                effective_payload = effective_payload.lower()
            elif self._mutant_enabled(request, 'M21') and request.compiler == 'clang':
                effective_payload = self._corrupt_payload(effective_payload)
            elif self._mutant_enabled(request, 'M22') and request.optimization == 'Os':
                effective_payload = self._corrupt_payload(effective_payload)
            elif self._mutant_enabled(request, 'M24') and signature_count == 2:
                effective_payload = self._corrupt_payload(effective_payload)
            if self._mutant_enabled(request, 'M12'):
                include_carrier = False

        key_ignored = request.marked and self.mutant_id == 'M06'
        source_text = request.host.read_text()
        if request.marked and self.mutant_id == 'M10':
            source_text = '#define WM_SEM_PLUS_ONE 1\n' + source_text
        if self.mutant_id == 'M11' and (request.marked or self.pilot):
            source_text = '#define WM_SEM_INPUT13 1\n' + source_text
        if self.mutant_id == 'M10' and self.pilot and not request.marked:
            source_text = '#define WM_SEM_PLUS_ONE 1\n' + source_text

        if include_carrier and self.carrier == 'string':
            record = make_record(effective_payload, request.key, key_ignored=key_ignored)
            values = ','.join(str(b) for b in record)
            source_text += f'\nstatic const unsigned char wm_record[] __attribute__((used,section(".rodata.wm"))) = {{{values}}};\n'
        elif include_carrier and self.carrier == 'symbol':
            declarations = []
            for index, name in enumerate(symbol_names(effective_payload, request.key, key_ignored=key_ignored)):
                declarations.append(f'const unsigned char {name} __attribute__((used,visibility("default"))) = {index + 1};')
            source_text += '\n' + '\n'.join(declarations) + '\n'

        source_path.write_text(source_text)
        requested_compiler = request.compiler
        requested_opt = request.optimization
        actual_compiler = 'gcc' if self.mutant_id == 'M13' else requested_compiler
        actual_opt = 'O0' if self.mutant_id == 'M14' else requested_opt
        compile_flags, link_flags = _host_compile_flags(request.host)
        command = [actual_compiler, '-std=c11', '-fno-ident', '-no-pie', f'-{actual_opt}', *compile_flags, str(source_path), '-o', str(binary_path), *link_flags]
        proc = subprocess.run(command, text=True, capture_output=True, timeout=20)
        if proc.returncode != 0:
            raise RuntimeError(f'compiler failed ({actual_compiler}): {proc.stderr.strip()}')

        if include_carrier and self.carrier == 'section':
            record_path = build_dir / 'record.bin'
            record_path.write_bytes(make_record(effective_payload, request.key, key_ignored=key_ignored))
            proc2 = subprocess.run(
                ['objcopy', '--add-section', f'.wmrec={record_path}', '--set-section-flags', '.wmrec=readonly,noload', str(binary_path)],
                text=True, capture_output=True, timeout=10
            )
            if proc2.returncode != 0:
                raise RuntimeError(f'objcopy add-section failed: {proc2.stderr.strip()}')
            record_path.unlink(missing_ok=True)

        result = BuildResult(
            binary=binary_path,
            source=source_path,
            requested_compiler=requested_compiler,
            actual_compiler=Path(actual_compiler).name,
            requested_optimization=requested_opt,
            actual_optimization=actual_opt,
            carrier=self.carrier,
            mutant_id=self.mutant_id,
            command=command,
            source_sha256=sha256_bytes(source_path.read_bytes()),
            binary_sha256=sha256_bytes(binary_path.read_bytes()),
            return_code=proc.returncode,
            stderr=proc.stderr.strip(),
            requested_payload_hex=requested_payload.hex(),
            effective_payload_hex=effective_payload.hex(),
            key=request.key,
        )
        self.original_paths.add(binary_path.resolve())

        if request.marked and self.mutant_id == 'M07':
            sidecar = binary_path.with_name(binary_path.name + '.wm-sidecar.json')
            sidecar.write_text(json.dumps({'key': request.key, 'payload_hex': requested_payload.hex()}, sort_keys=True))
        if request.marked and self.mutant_id == 'M08':
            self.latest_payload = requested_payload
            self.latest_key = request.key
        if request.marked and self.mutant_id == 'M18' and self.first_marked_result is None:
            self.first_marked_result = result
        return result

    def _extract_carrier(self, binary: Path, key: str, *, validation: bool = False) -> bytes:
        key_ignored = self.mutant_id == 'M06'
        checksum_bypass = self.mutant_id == 'M16' and not validation
        if self.carrier == 'string':
            return parse_record(binary.read_bytes(), key, key_ignored=key_ignored, checksum_bypass=checksum_bypass)
        if self.carrier == 'symbol':
            return parse_symbols(binary, key, key_ignored=key_ignored, checksum_bypass=checksum_bypass)
        dump_path = binary.parent / f'.dump-{os.getpid()}-{binary.name}'
        proc = subprocess.run(['objcopy', '--dump-section', f'.wmrec={dump_path}', str(binary)], text=True, capture_output=True, timeout=10)
        try:
            if proc.returncode != 0 or not dump_path.exists():
                raise ExtractionError('absent', 'custom section .wmrec not found')
            return parse_record(dump_path.read_bytes(), key, key_ignored=key_ignored, checksum_bypass=checksum_bypass)
        finally:
            dump_path.unlink(missing_ok=True)

    def extract_for_validation(self, binary: Path, key: str) -> bytes:
        return self._extract_carrier(binary, key, validation=True)

    def extract(self, binary: Path, key: str) -> bytes:
        try:
            if self.mutant_id == 'M17' and binary.resolve() not in self.original_paths:
                raise ExtractionError('path', 'artifact path is not an original build path')
            if self.mutant_id == 'M08' and self.latest_payload is not None:
                payload = self.latest_payload
            elif (self.mutant_id == 'M23' and self._last_extracted_payload is not None
                  and binary.resolve() in self._extracted_binaries
                  and self._last_extracted_binary != binary.resolve()):
                payload = self._last_extracted_payload
            elif self.mutant_id == 'M07':
                sidecar = binary.with_name(binary.name + '.wm-sidecar.json')
                if not sidecar.exists():
                    raise ExtractionError('sidecar', 'adjacent sidecar is missing')
                row = json.loads(sidecar.read_text())
                if row['key'] != key:
                    raise ExtractionError('wrong-key', 'sidecar key mismatch')
                payload = bytes.fromhex(row['payload_hex'])
            else:
                payload = self._extract_carrier(binary, key, validation=False)
        except ExtractionError:
            if self.mutant_id == 'M09':
                payload = b'Morph-01'
            else:
                raise
        if self.mutant_id == 'M19':
            payload = payload[:-1]
        if self.mutant_id == 'M23':
            resolved = binary.resolve()
            self._extracted_binaries.add(resolved)
            self._last_extracted_binary = resolved
            self._last_extracted_payload = payload
        return payload

    def _candidate_remove_carrier(self, result: BuildResult, target_dir: Path) -> Path:
        target = target_dir / 'removed.bin'
        self._copy_context(result.binary, target)
        if self.mutant_id == 'M15':
            return target
        if self.carrier == 'string':
            data = bytearray(target.read_bytes())
            pos = data.find(MAGIC)
            if pos >= 0:
                data[pos:pos + len(MAGIC)] = b'XXXX'
                target.write_bytes(data)
        elif self.carrier == 'symbol':
            proc = subprocess.run(['strip', '-s', str(target)], text=True, capture_output=True, timeout=10)
            if proc.returncode != 0:
                raise RuntimeError(f'strip failed: {proc.stderr.strip()}')
        else:
            proc = subprocess.run(['objcopy', '--remove-section', '.wmrec', str(target)], text=True, capture_output=True, timeout=10)
            if proc.returncode != 0:
                raise RuntimeError(f'objcopy remove-section failed: {proc.stderr.strip()}')
        return target

    def corrupt_carrier(self, result: BuildResult, target_dir: Path) -> Path:
        target = target_dir / 'corrupt.bin'
        self._copy_context(result.binary, target)
        # M18 models reuse of a previously materialized binary when byte/section variants are requested.
        if self.mutant_id == 'M18' and self.carrier in {'string', 'section'}:
            return target
        if self.carrier == 'string':
            data = bytearray(target.read_bytes())
            start, end = locate_record(bytes(data))
            data[end - 1] ^= 1
            target.write_bytes(data)
        elif self.carrier == 'section':
            dump = target_dir / 'section.bin'
            proc = subprocess.run(['objcopy', '--dump-section', f'.wmrec={dump}', str(target)], text=True, capture_output=True, timeout=10)
            if proc.returncode != 0 or not dump.exists():
                raise ExtractionError('absent', 'cannot corrupt absent custom section')
            data = bytearray(dump.read_bytes())
            _, end = locate_record(bytes(data))
            data[end - 1] ^= 1
            dump.write_bytes(data)
            proc2 = subprocess.run(['objcopy', '--update-section', f'.wmrec={dump}', str(target)], text=True, capture_output=True, timeout=10)
            if proc2.returncode != 0:
                raise RuntimeError(f'objcopy update-section failed: {proc2.stderr.strip()}')
            dump.unlink(missing_ok=True)
        else:
            proc = subprocess.run(['nm', '-g', str(target)], text=True, capture_output=True, timeout=5)
            names = [line.split()[-1] for line in proc.stdout.splitlines() if line.split() and line.split()[-1].startswith('wmrec_')]
            if not names:
                return target
            selected = names[:1] if self.pilot else names
            mapping = []
            for old in selected:
                parts = old.split('_')
                parts[-1] = '0000000000000000'
                mapping.append(f'{old} {"_".join(parts)}')
            map_path = target_dir / 'rename.map'
            map_path.write_text('\n'.join(mapping) + '\n')
            proc2 = subprocess.run(['objcopy', f'--redefine-syms={map_path}', str(target)], text=True, capture_output=True, timeout=10)
            if proc2.returncode != 0:
                raise RuntimeError(f'objcopy redefine-syms failed: {proc2.stderr.strip()}')
        return target


def run_host(binary: Path, value: int) -> str:
    proc = subprocess.run([str(binary), str(value)], text=True, capture_output=True, timeout=5)
    if proc.returncode != 0:
        raise RuntimeError(f'host returned {proc.returncode}: {proc.stderr.strip()}')
    return proc.stdout.strip()


def remove_carrier(self, result, target_dir):
    def _parse(candidate_blob):
        return _candidate_remove_carrier(candidate_blob, target_dir)
    def _absent():
        return _candidate_remove_carrier(result, target_dir)
    return first_valid_candidate(result, MAGIC, _parse, _absent)
