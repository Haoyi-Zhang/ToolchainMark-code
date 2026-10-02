"""Evidence-gated relation execution.

This module does not modify the retained legacy matrices. It evaluates the same
14 relation intents with explicit construction evidence, typed observations,
and a verdict that distinguishes invalid experiments from contract violations.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import shutil

from .model import BuildRequest, BuildResult, ExtractionError
from .pipeline import Pipeline, run_host
from .relations import INPUTS, KEY1, KEY2, PAYLOAD1, PAYLOAD2

VERDICTS = frozenset({'SATISFIED', 'INCONSISTENT', 'INADMISSIBLE'})
DOMAIN_REJECTIONS = frozenset({'absent', 'wrong-key', 'checksum', 'malformed', 'version', 'path', 'sidecar'})


class InadmissibleCase(RuntimeError):
    """An experiment cannot yet justify an implementation verdict."""


@dataclass
class Evidence:
    phase: str = 'construction'
    facts: dict[str, bool] = field(default_factory=dict)
    observations: dict[str, Any] = field(default_factory=dict)

    def require(self, name: str, condition: bool) -> None:
        self.facts[name] = bool(condition)
        if not condition:
            raise InadmissibleCase(name)


@dataclass(frozen=True)
class ScientificOutcome:
    verdict: str
    reason: str
    phase: str
    admission: dict[str, bool]
    observations: dict[str, Any]

    @property
    def exposed(self) -> bool:
        return self.verdict == 'INCONSISTENT'


def extract_observation(pipeline: Pipeline, binary: Path, key: str) -> dict[str, str]:
    """Typed domain rejection is an observation; tool/process failure is not."""
    try:
        return {'kind': 'payload', 'value': pipeline.extract(binary, key).hex()}
    except ExtractionError as exc:
        if exc.kind not in DOMAIN_REJECTIONS:
            raise RuntimeError('observer-tool-failure:' + exc.kind) from exc
        return {'kind': 'rejection', 'value': exc.kind}


def payload_matches(obs: dict[str, str], expected: bytes) -> bool:
    return obs == {'kind': 'payload', 'value': expected.hex()}


def inspect_carrier(carrier: str, binary: Path, key: str) -> dict[str, str]:
    """Seed-free observer; shares record parser, not pipeline mutation state.

    This is not an independently implemented parser. The shared-parser trust
    boundary is reported in the manuscript and replication documentation.
    """
    observer = Pipeline(carrier, 'CLEAN')
    return extract_observation(observer, binary, key)


def evaluate(relation: str, pipeline: Pipeline, host: Path, root: Path) -> ScientificOutcome:
    evidence = Evidence()
    try:
        ok = _evaluate(relation, pipeline, host, root, evidence)
        return ScientificOutcome('SATISFIED' if ok else 'INCONSISTENT',
                                 'predicate-satisfied' if ok else 'predicate-violated',
                                 evidence.phase, dict(evidence.facts), dict(evidence.observations))
    except InadmissibleCase as exc:
        return ScientificOutcome('INADMISSIBLE', str(exc), evidence.phase,
                                 dict(evidence.facts), dict(evidence.observations))
    except Exception as exc:
        # Do not convert a timeout, unavailable utility, I/O error, or compiler
        # failure into a mutant kill. Exception text can contain private paths;
        # preserve the type and phase here rather than a machine-local message.
        return ScientificOutcome('INADMISSIBLE', 'execution-error:' + type(exc).__name__,
                                 evidence.phase, dict(evidence.facts), dict(evidence.observations))


def _evaluate(relation: str, pipeline: Pipeline, host: Path, root: Path, e: Evidence) -> bool:
    if relation not in {f'MR{i:02d}' for i in range(1, 15)}:
        raise ValueError('unknown relation')
    e.require('subject_exists', host.is_file())
    e.require('isolated_workspace', not root.exists() or not any(root.iterdir()))
    root.mkdir(parents=True, exist_ok=True)

    def build(label: str, payload: bytes = PAYLOAD1, compiler: str = 'gcc',
              optimization: str = 'O2', marked: bool = True, guarded: bool = False) -> BuildResult:
        result = pipeline.build(BuildRequest(host, payload, KEY1, compiler, optimization,
                                            root / label, marked, guarded))
        if result.return_code != 0 or not result.binary.is_file():
            raise InadmissibleCase('artifact_construction_failed')
        return result

    def outputs(binary: Path) -> list[str]:
        return [run_host(binary, value) for value in INPUTS]

    def observe(result: BuildResult, key: str = KEY1) -> dict[str, str]:
        return extract_observation(pipeline, result.binary, key)

    def source_valid(result: BuildResult, physical: bool = False) -> dict[str, str]:
        e.phase = 'source-admission'
        obs = observe(result)
        e.observations['source'] = obs
        e.require('source_payload_recovered', payload_matches(obs, PAYLOAD1))
        if physical:
            obs2 = inspect_carrier(pipeline.carrier, result.binary, KEY1)
            e.observations['source_carrier'] = obs2
            e.require('source_carrier_valid', payload_matches(obs2, PAYLOAD1))
        return obs

    if relation == 'MR01':
        result = build('marked'); e.phase = 'payload-observation'
        obs = observe(result); e.observations['extraction'] = obs
        return payload_matches(obs, PAYLOAD1)
    if relation == 'MR02':
        base = build('unmarked', marked=False); marked = build('marked')
        e.phase = 'host-observation'
        left, right = outputs(base.binary), outputs(marked.binary)
        e.require('both_hosts_terminate', True)
        e.observations['mismatches'] = [{'input': x, 'base': a, 'marked': b}
                                       for x, a, b in zip(INPUTS, left, right) if a != b]
        return left == right
    if relation == 'MR03':
        base = build('unmarked', marked=False); e.phase = 'absence-admission'
        physical = inspect_carrier(pipeline.carrier, base.binary, KEY1)
        e.observations['carrier'] = physical
        e.require('carrier_absent', physical == {'kind': 'rejection', 'value': 'absent'})
        e.phase = 'rejection-observation'; obs = observe(base); e.observations['extraction'] = obs
        return obs == {'kind': 'rejection', 'value': 'absent'}
    if relation == 'MR04':
        base = build('source', guarded=True); source_valid(base)
        e.require('keys_distinct', KEY1 != KEY2)
        e.phase = 'wrong-key-observation'; obs = observe(base, KEY2); e.observations['followup'] = obs
        return obs == {'kind': 'rejection', 'value': 'wrong-key'}
    if relation == 'MR05':
        first = build('first'); second = build('second', payload=PAYLOAD2)
        e.phase = 'separation-observation'; a, b = observe(first), observe(second)
        e.observations.update(first=a, second=b, execution_order='sequential-builds-then-extract')
        return payload_matches(a, PAYLOAD1) and payload_matches(b, PAYLOAD2) and a != b
    if relation in {'MR06', 'MR07'}:
        settings = [('gcc', 'O2'), ('clang', 'O2')] if relation == 'MR06' else [('gcc', x) for x in ('O0', 'O2', 'Os')]
        results = [build(f'branch-{i}', compiler=c, optimization=o) for i, (c, o) in enumerate(settings)]
        e.phase = 'build-intervention-admission'
        e.observations['builds'] = [{'requested': [c, o], 'actual': [r.actual_compiler, r.actual_optimization]}
                                    for r, (c, o) in zip(results, settings)]
        e.require('requested_branches_executed', all(r.actual_compiler == c and r.actual_optimization == o
                                                    for r, (c, o) in zip(results, settings)))
        e.phase = 'branch-observation'; observations = [observe(r) for r in results]
        host_outputs = [outputs(r.binary) for r in results]
        e.require('branch_hosts_terminate', True)
        e.observations.update(extractions=observations, host_outputs_agree=all(x == host_outputs[0] for x in host_outputs))
        return all(payload_matches(x, PAYLOAD1) for x in observations) and all(x == host_outputs[0] for x in host_outputs)
    if relation == 'MR08':
        base = build('source'); source_valid(base)
        e.phase = 'relocation-admission'; source_bytes = base.binary.read_bytes(); source_outputs = outputs(base.binary)
        clean = root / 'destination'; clean.mkdir()
        target = clean / 'program'; shutil.copy2(base.binary, target)
        e.require('artifact_bytes_preserved', target.read_bytes() == source_bytes)
        e.require('only_artifact_relocated', sorted(x.name for x in clean.iterdir()) == ['program'])
        e.phase = 'relocation-observation'; obs = extract_observation(pipeline, target, KEY1)
        target_outputs = outputs(target); e.require('relocated_host_terminates', True)
        e.observations.update(followup=obs, host_outputs_agree=source_outputs == target_outputs)
        return payload_matches(obs, PAYLOAD1) and source_outputs == target_outputs
    if relation in {'MR09', 'MR10'}:
        base = build('source', guarded=True); source_valid(base, physical=True)
        e.phase = 'intervention-admission'
        target = (pipeline.remove_carrier if relation == 'MR09' else pipeline.corrupt_carrier)(base, root / 'followup')
        physical = inspect_carrier(pipeline.carrier, target, KEY1)
        e.observations['followup_carrier'] = physical
        expected = 'absent' if relation == 'MR09' else 'checksum'
        e.require('carrier_removed' if relation == 'MR09' else 'integrity_corruption_established',
                  physical == {'kind': 'rejection', 'value': expected})
        e.phase = 'rejection-observation'; obs = extract_observation(pipeline, target, KEY1)
        e.observations['followup'] = obs
        return obs == {'kind': 'rejection', 'value': expected}
    if relation == 'MR11':
        result = build('requested', compiler='clang', optimization='Os'); e.phase = 'trace-observation'
        e.observations.update(requested=['clang', 'Os'], actual=[result.actual_compiler, result.actual_optimization])
        return result.actual_compiler == 'clang' and result.actual_optimization == 'Os'
    if relation == 'MR12':
        pipeline.begin_overlapping_builds(2)
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                first_f = pool.submit(build, 'first', PAYLOAD1)
                second_f = pool.submit(build, 'second', PAYLOAD2)
                first, second = first_f.result(), second_f.result()
        finally:
            pipeline.end_overlapping_builds()
        e.require('staging_rendezvous_completed', True)
        e.phase = 'concurrent-observation'; a, b = observe(first), observe(second)
        ok = payload_matches(a, PAYLOAD1) and payload_matches(b, PAYLOAD2) and a != b
        # The identity of a racing winner is not a stable scientific observation.
        e.observations.update(both_expected=ok, outputs_distinct=a != b,
                              both_payloads=a['kind'] == b['kind'] == 'payload',
                              execution_order='overlapping-builds-then-extract')
        return ok
    if relation == 'MR13':
        first = build('first'); second = build('second', payload=PAYLOAD2)
        e.phase = 'order-observation'; before = observe(first); intervening = observe(second); after = observe(first)
        e.observations.update(before=before, intervening=intervening, after=after)
        return payload_matches(before, PAYLOAD1) and payload_matches(intervening, PAYLOAD2) and payload_matches(after, PAYLOAD1)
    if relation == 'MR14':
        first = build('first'); before = observe(first); second = build('second'); after = observe(second)
        e.phase = 'rebuild-observation'; e.observations.update(before=before, after=after)
        return payload_matches(before, PAYLOAD1) and payload_matches(after, PAYLOAD1)
    raise AssertionError('unreachable')
