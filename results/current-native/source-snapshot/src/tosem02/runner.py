from __future__ import annotations

import csv
import hashlib
import json
import shutil
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .catalog import artifact_root, load_mutants, load_relations, mutant_map, relation_map
from .pipeline import Pipeline
from .relations import HANDLERS

CARRIERS = ['string', 'symbol', 'section']
BREADTH_RELATIONS = ['MR01', 'MR02', 'MR06', 'MR07']


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonicalize_runtime_paths(value: Any, work_root: Path) -> Any:
    """Replace machine-local experiment paths with a stable logical root.

    Raw result rows retain trace structure and filenames, but never depend on or
    disclose the absolute temporary directory chosen by the executing machine.
    """
    if isinstance(value, dict):
        return {key: _canonicalize_runtime_paths(item, work_root) for key, item in value.items()}
    if isinstance(value, list):
        return [_canonicalize_runtime_paths(item, work_root) for item in value]
    if isinstance(value, tuple):
        return tuple(_canonicalize_runtime_paths(item, work_root) for item in value)
    if isinstance(value, Path):
        value = str(value)
    if isinstance(value, str):
        prefix = str(work_root)
        if value == prefix:
            return 'WORKDIR'
        if value.startswith(prefix + '/'):
            return 'WORKDIR/' + value[len(prefix) + 1:]
    return value


def execute_task(task: dict[str, Any]) -> dict[str, Any]:
    relation_id = task['relation_id']
    carrier = task['carrier']
    mutant_id = task['mutant_id']
    host = Path(task['host'])
    pilot = bool(task.get('pilot', False))
    work = Path(task['work'])
    work_root = Path(task['work_root'])
    relation = relation_map()[relation_id]
    mutant = mutant_map().get(mutant_id, {'operator': 'clean', 'fault_class': 'clean'})
    started = time.perf_counter()
    exception_class = ''
    observations: dict[str, Any] = {}
    try:
        pipeline = Pipeline(carrier, mutant_id, pilot=pilot)
        outcome = HANDLERS[relation_id](pipeline, host, work)
        passed = outcome.passed
        detail = outcome.detail
        observations = outcome.observations
    except Exception as exc:  # Every infrastructure or subject exception is retained as a failed row.
        passed = False
        exception_class = type(exc).__name__
        detail = f'exception:{exception_class}:{str(exc).replace(chr(10), " ")[:500]}'
    duration = time.perf_counter() - started
    detail = _canonicalize_runtime_paths(detail, work_root)
    observations = _canonicalize_runtime_paths(observations, work_root)
    shutil.rmtree(work, ignore_errors=True)
    return {
        'surface': task['surface'],
        'host': host.name,
        'host_sha256': _sha(host),
        'carrier': carrier,
        'defect_id': mutant_id,
        'defect_operator': mutant['operator'],
        'fault_class': mutant['fault_class'],
        'relation_id': relation_id,
        'relation_name': relation['name'],
        'polarity': relation['polarity'],
        'pass': passed,
        'killed': (not passed) if mutant_id != 'CLEAN' else False,
        'detail': detail,
        'duration_seconds': round(duration, 6),
        'exception_class': exception_class,
        'pilot': pilot,
        'observations_json': json.dumps(observations, sort_keys=True, separators=(',', ':')),
    }


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ['surface', 'host', 'host_sha256', 'carrier', 'defect_id', 'defect_operator', 'fault_class',
              'relation_id', 'relation_name', 'polarity', 'pass', 'killed', 'detail', 'duration_seconds',
              'exception_class', 'pilot', 'observations_json']
    with path.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def run_catalog(output: Path, workers: int = 8, pilot: bool = False, work_root: Path | None = None) -> list[dict[str, Any]]:
    root = artifact_root()
    host = root / 'hosts/H01-gcd.c'
    relations = [row['id'] for row in load_relations()]
    mutants = [row['id'] for row in load_mutants()]
    tasks: list[dict[str, Any]] = []
    base_work = work_root or Path(tempfile.mkdtemp(prefix='tosem02-catalog-'))
    for carrier in CARRIERS:
        if not pilot:
            for relation_id in relations:
                tasks.append({'surface': 'clean_catalog', 'host': str(host), 'carrier': carrier, 'mutant_id': 'CLEAN',
                              'relation_id': relation_id, 'pilot': False, 'work_root': str(base_work),
                              'work': str(base_work / carrier / 'CLEAN' / relation_id)})
        for mutant_id in mutants:
            for relation_id in relations:
                tasks.append({'surface': 'pilot_mutation' if pilot else 'mutation', 'host': str(host), 'carrier': carrier,
                              'mutant_id': mutant_id, 'relation_id': relation_id, 'pilot': pilot,
                              'work_root': str(base_work), 'work': str(base_work / carrier / mutant_id / relation_id)})
    rows: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=max(1, min(workers, 8))) as pool:
        futures = [pool.submit(execute_task, task) for task in tasks]
        for future in as_completed(futures):
            rows.append(future.result())
    rows.sort(key=lambda row: (CARRIERS.index(row['carrier']), row['defect_id'] != 'CLEAN', row['defect_id'], row['relation_id']))
    _write_rows(output, rows)
    shutil.rmtree(base_work, ignore_errors=True)
    return rows


def run_breadth(output: Path, workers: int = 8, work_root: Path | None = None) -> list[dict[str, Any]]:
    root = artifact_root()
    hosts = sorted((root / 'hosts').glob('H*.c'))
    base_work = work_root or Path(tempfile.mkdtemp(prefix='tosem02-breadth-'))
    tasks: list[dict[str, Any]] = []
    for host in hosts:
        for carrier in CARRIERS:
            for relation_id in BREADTH_RELATIONS:
                tasks.append({'surface': 'clean_breadth', 'host': str(host), 'carrier': carrier, 'mutant_id': 'CLEAN',
                              'relation_id': relation_id, 'pilot': False, 'work_root': str(base_work),
                              'work': str(base_work / host.stem / carrier / relation_id)})
    rows: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=max(1, min(workers, 8))) as pool:
        futures = [pool.submit(execute_task, task) for task in tasks]
        for future in as_completed(futures):
            rows.append(future.result())
    rows.sort(key=lambda row: (row['host'], CARRIERS.index(row['carrier']), row['relation_id']))
    _write_rows(output, rows)
    shutil.rmtree(base_work, ignore_errors=True)
    return rows


def run_robustness(output: Path, workers: int = 8, work_root: Path | None = None) -> list[dict[str, Any]]:
    """Execute the complete clean-plus-defect relation matrix over every subject."""
    root = artifact_root()
    hosts = sorted((root / 'hosts').glob('H*.c'))
    relations = [row['id'] for row in load_relations()]
    defects = ['CLEAN'] + [row['id'] for row in load_mutants()]
    base_work = work_root or Path(tempfile.mkdtemp(prefix='tosem02-robustness-'))
    tasks: list[dict[str, Any]] = []
    for host in hosts:
        for carrier in CARRIERS:
            for defect_id in defects:
                surface = 'robustness_clean' if defect_id == 'CLEAN' else 'robustness_mutation'
                for relation_id in relations:
                    tasks.append({
                        'surface': surface, 'host': str(host), 'carrier': carrier, 'mutant_id': defect_id,
                        'relation_id': relation_id, 'pilot': False, 'work_root': str(base_work),
                        'work': str(base_work / host.stem / carrier / defect_id / relation_id),
                    })
    rows: list[dict[str, Any]] = []
    total = len(tasks)
    with ProcessPoolExecutor(max_workers=max(1, min(workers, 8))) as pool:
        futures = [pool.submit(execute_task, task) for task in tasks]
        for index, future in enumerate(as_completed(futures), 1):
            rows.append(future.result())
            if index % 500 == 0 or index == total:
                print(f'robustness progress: {index}/{total}', flush=True)
    rows.sort(key=lambda row: (row['host'], CARRIERS.index(row['carrier']), row['defect_id'] != 'CLEAN', row['defect_id'], row['relation_id']))
    _write_rows(output, rows)
    shutil.rmtree(base_work, ignore_errors=True)
    return rows


# Evidence-preserving wrapper installed after the original task implementation.
from .trace_runtime import trace_session, install_pipeline_method_tracing, install_subprocess_proxy
from . import pipeline as _tosem02_pipeline_module
install_subprocess_proxy(_tosem02_pipeline_module)
if hasattr(_tosem02_pipeline_module, 'Pipeline'):
    install_pipeline_method_tracing(_tosem02_pipeline_module.Pipeline)
_tosem02_original_execute_task = execute_task

def execute_task(task):
    with trace_session(task) as _trace:
        row = _tosem02_original_execute_task(task)
    if not isinstance(row, dict):
        return row
    row.update(_trace.row_fields())
    row['per_input_observations_json'] = row.get('observations_json', row.get('observations', '{}'))
    exception = str(row.get('exception_class') or '')
    detail = str(row.get('detail') or '')
    if exception in {'ToolObservationError', 'ObservationUnavailable'} or 'ToolObservationError' in detail or 'ObservationUnavailable' in detail:
        row['admission_outcome'] = 'INADMISSIBLE'
    else:
        row['admission_outcome'] = 'ADMITTED'
    return row
