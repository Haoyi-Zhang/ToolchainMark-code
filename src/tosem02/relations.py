from __future__ import annotations

import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .model import BuildRequest, ExtractionError, RelationOutcome
from .pipeline import Pipeline, run_host

PAYLOAD1 = b'Morph-01'
PAYLOAD2 = b'Second-2'
KEY1 = 'key-alpha'
KEY2 = 'key-beta'
INPUTS = [0, 1, 5, 13, 144, 99991]


def _build(pipeline: Pipeline, host: Path, root: Path, label: str, payload: bytes = PAYLOAD1, key: str = KEY1,
           compiler: str = 'gcc', optimization: str = 'O2', marked: bool = True,
           guard_upstream: bool = False):
    return pipeline.build(BuildRequest(host, payload, key, compiler, optimization, root / label, marked, guard_upstream))


def _obs(binary: Path) -> list[str]:
    return [run_host(binary, value) for value in INPUTS]


def _expected_rejection(fn) -> tuple[bool, str]:
    try:
        value = fn()
        return False, f'accepted:{value!r}'
    except ExtractionError as exc:
        return True, f'rejected:{exc.kind}:{exc.message}'


def mr01_roundtrip(pipeline: Pipeline, host: Path, root: Path) -> RelationOutcome:
    result = _build(pipeline, host, root, 'marked')
    value = pipeline.extract(result.binary, KEY1)
    passed = value == PAYLOAD1
    return RelationOutcome(passed, f'extracted={value!r}', {'build': result.to_dict(), 'extracted_hex': value.hex()})


def mr02_semantics(pipeline: Pipeline, host: Path, root: Path) -> RelationOutcome:
    base = _build(pipeline, host, root, 'base', marked=False)
    marked = _build(pipeline, host, root, 'marked')
    base_outputs = _obs(base.binary)
    marked_outputs = _obs(marked.binary)
    mismatches = [
        {'input': value, 'base': base_outputs[i], 'marked': marked_outputs[i]}
        for i, value in enumerate(INPUTS) if base_outputs[i] != marked_outputs[i]
    ]
    return RelationOutcome(not mismatches, f'mismatch_count={len(mismatches)}', {'mismatches': mismatches})


def mr03_unmarked_rejection(pipeline: Pipeline, host: Path, root: Path) -> RelationOutcome:
    result = _build(pipeline, host, root, 'unmarked', marked=False)
    passed, detail = _expected_rejection(lambda: pipeline.extract(result.binary, KEY1))
    return RelationOutcome(passed, detail, {'unmarked_binary_sha256': result.binary_sha256})


def mr04_wrong_key(pipeline: Pipeline, host: Path, root: Path) -> RelationOutcome:
    result = _build(pipeline, host, root, 'source', guard_upstream=True)
    antecedent = pipeline.extract_for_validation(result.binary, KEY1)
    if antecedent != PAYLOAD1:
        return RelationOutcome(False, f'antecedent_mismatch={antecedent!r}', {'antecedent_hex': antecedent.hex(), 'antecedent_guarded': True})
    passed, detail = _expected_rejection(lambda: pipeline.extract(result.binary, KEY2))
    return RelationOutcome(passed, detail, {'antecedent_guarded': True, 'antecedent_hex': antecedent.hex()})


def mr05_payload_separation(pipeline: Pipeline, host: Path, root: Path) -> RelationOutcome:
    # Sequential builds: the second request begins only after the first build completes.
    first = _build(pipeline, host, root, 'first', payload=PAYLOAD1)
    second = _build(pipeline, host, root, 'second', payload=PAYLOAD2)
    v1 = pipeline.extract(first.binary, KEY1)
    v2 = pipeline.extract(second.binary, KEY1)
    passed = v1 == PAYLOAD1 and v2 == PAYLOAD2 and v1 != v2
    return RelationOutcome(passed, f'first={v1!r};second={v2!r}', {'first_hex': v1.hex(), 'second_hex': v2.hex(), 'execution_order': 'sequential-builds-then-extract'})


def mr06_cross_compiler(pipeline: Pipeline, host: Path, root: Path) -> RelationOutcome:
    gcc = _build(pipeline, host, root, 'gcc', compiler='gcc', optimization='O2')
    clang = _build(pipeline, host, root, 'clang', compiler='clang', optimization='O2')
    vg = pipeline.extract(gcc.binary, KEY1)
    vc = pipeline.extract(clang.binary, KEY1)
    og = _obs(gcc.binary)
    oc = _obs(clang.binary)
    passed = vg == PAYLOAD1 and vc == PAYLOAD1 and og == oc
    return RelationOutcome(passed, f'payloads={vg!r},{vc!r};semantic_equal={og == oc}', {'gcc_actual': gcc.actual_compiler, 'clang_actual': clang.actual_compiler})


def mr07_optimization(pipeline: Pipeline, host: Path, root: Path) -> RelationOutcome:
    results = [_build(pipeline, host, root, opt, compiler='gcc', optimization=opt) for opt in ['O0', 'O2', 'Os']]
    payloads = [pipeline.extract(row.binary, KEY1) for row in results]
    outputs = [_obs(row.binary) for row in results]
    passed = all(value == PAYLOAD1 for value in payloads) and outputs[0] == outputs[1] == outputs[2]
    return RelationOutcome(passed, f'payloads={[value.decode("latin1") for value in payloads]};semantic_equal={outputs[0] == outputs[1] == outputs[2]}', {})


def mr08_relocation(pipeline: Pipeline, host: Path, root: Path) -> RelationOutcome:
    result = _build(pipeline, host, root, 'source')
    source_value = pipeline.extract(result.binary, KEY1)
    if source_value != PAYLOAD1:
        return RelationOutcome(False, f'source_mismatch={source_value!r}', {'source_hex': source_value.hex()})
    clean = root / 'clean-room'
    clean.mkdir(parents=True, exist_ok=True)
    relocated = clean / 'renamed-artifact.bin'
    shutil.copy2(result.binary, relocated)
    value = pipeline.extract(relocated, KEY1)
    passed = value == PAYLOAD1
    return RelationOutcome(passed, f'relocated={value!r}', {'relocated_hex': value.hex(), 'clean_room_entries': [p.name for p in clean.iterdir()]})


def mr09_removal(pipeline: Pipeline, host: Path, root: Path) -> RelationOutcome:
    result = _build(pipeline, host, root, 'source', guard_upstream=True)
    antecedent = pipeline.extract_for_validation(result.binary, KEY1)
    if antecedent != PAYLOAD1:
        return RelationOutcome(False, f'antecedent_mismatch={antecedent!r}', {'antecedent_guarded': True})
    removed = pipeline.remove_carrier(result, root / 'follow-up')
    passed, detail = _expected_rejection(lambda: pipeline.extract(removed, KEY1))
    return RelationOutcome(passed, detail if passed else f'spurious robustness:{detail}', {'antecedent_guarded': True})


def mr10_corruption(pipeline: Pipeline, host: Path, root: Path) -> RelationOutcome:
    result = _build(pipeline, host, root, 'source', guard_upstream=True)
    antecedent = pipeline.extract_for_validation(result.binary, KEY1)
    if antecedent != PAYLOAD1:
        return RelationOutcome(False, f'antecedent_mismatch={antecedent!r}', {'antecedent_guarded': True})
    corrupt = pipeline.corrupt_carrier(result, root / 'follow-up')
    passed, detail = _expected_rejection(lambda: pipeline.extract(corrupt, KEY1))
    return RelationOutcome(passed, detail if passed else f'corruption accepted:{detail}', {'antecedent_guarded': True})


def mr11_trace(pipeline: Pipeline, host: Path, root: Path) -> RelationOutcome:
    result = _build(pipeline, host, root, 'trace', compiler='clang', optimization='Os')
    passed = result.actual_compiler == 'clang' and result.actual_optimization == 'Os'
    detail = f'requested=clang/Os;actual={result.actual_compiler}/{result.actual_optimization}'
    return RelationOutcome(passed, detail, {'build': result.to_dict()})


def mr12_interleaved(pipeline: Pipeline, host: Path, root: Path) -> RelationOutcome:
    # Both requests rendezvous at the staging point before either compilation proceeds.
    pipeline.begin_overlapping_builds(2)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first_future = pool.submit(_build, pipeline, host, root, 'first', PAYLOAD1, KEY1)
            second_future = pool.submit(_build, pipeline, host, root, 'second', PAYLOAD2, KEY1)
            first = first_future.result()
            second = second_future.result()
    finally:
        pipeline.end_overlapping_builds()
    v1 = pipeline.extract(first.binary, KEY1)
    v2 = pipeline.extract(second.binary, KEY1)
    passed = v1 == PAYLOAD1 and v2 == PAYLOAD2
    detail = 'parallel_isolation_satisfied' if passed else 'parallel_isolation_clause_violated'
    return RelationOutcome(passed, detail, {'execution_order': 'overlapping-builds-then-extract', 'both_expected': passed, 'payloads_distinct': v1 != v2, 'aliasing_detected': v1 == v2})


def mr13_reordered(pipeline: Pipeline, host: Path, root: Path) -> RelationOutcome:
    first = _build(pipeline, host, root, 'first', payload=PAYLOAD1, key=KEY1, compiler='gcc', optimization='O2')
    before = pipeline.extract(first.binary, KEY1)
    unrelated = _build(pipeline, host, root, 'unrelated', payload=PAYLOAD2, key=KEY2, compiler='gcc', optimization='O2')
    intervening = pipeline.extract(unrelated.binary, KEY2)
    after = pipeline.extract(first.binary, KEY1)
    passed = before == PAYLOAD1 and intervening == PAYLOAD2 and after == PAYLOAD1
    return RelationOutcome(passed, f'before={before!r};intervening={intervening!r};after={after!r}', {'intervening_extraction': True})


def mr14_rebuild(pipeline: Pipeline, host: Path, root: Path) -> RelationOutcome:
    first = _build(pipeline, host, root, 'first')
    v1 = pipeline.extract(first.binary, KEY1)
    second = _build(pipeline, host, root, 'second')
    v2 = pipeline.extract(second.binary, KEY1)
    passed = v1 == PAYLOAD1 and v2 == PAYLOAD1
    return RelationOutcome(passed, f'first={v1!r};second={v2!r}', {'binary_bytes_equal': first.binary_sha256 == second.binary_sha256, 'execution_order': 'build1-extract1-build2-extract2'})


HANDLERS = {
    'MR01': mr01_roundtrip,
    'MR02': mr02_semantics,
    'MR03': mr03_unmarked_rejection,
    'MR04': mr04_wrong_key,
    'MR05': mr05_payload_separation,
    'MR06': mr06_cross_compiler,
    'MR07': mr07_optimization,
    'MR08': mr08_relocation,
    'MR09': mr09_removal,
    'MR10': mr10_corruption,
    'MR11': mr11_trace,
    'MR12': mr12_interleaved,
    'MR13': mr13_reordered,
    'MR14': mr14_rebuild,
}
