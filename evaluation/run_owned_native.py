"""Separate fixed native workflow and same-observation integrity comparison.

Raw objects, inputs, action observations and timings are retained. No original
Linux matrix is overwritten or inferred to execute. Use --replay for actual
recompilation/object loading, not merely recomputing generated counts.
"""
from __future__ import annotations
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import platform
import sys
import tempfile
import time
from unittest.mock import patch

from tosem02.admission import evaluate
from tosem02.relations import INPUTS, KEY1
from owned_native_tool.adapter import OwnedPipeline, direct_integrity
from owned_native_tool import tool

RELATIONS = ('MR01','MR02','MR03','MR04','MR05','MR08','MR09','MR10','MR13','MR14')
INTERVENTIONS = ('checksum','none','payload','both','outside','restore')


def versions():
    root = Path(__file__).resolve().parents[1]
    paths = ('src/tosem02/admission.py','src/tosem02/integrity.py','src/tosem02/record.py',
             'owned_native_tool/tool.py','owned_native_tool/adapter.py','evaluation/run_owned_native.py')
    return {p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths}


def plan(small):
    for family in tool.FAMILIES[:1] if small else tool.FAMILIES:
        for variant in range(1 if small else 4):
            for profile in tool.PROFILES:
                for relation in RELATIONS:
                    yield family,variant,profile,'clean-workflow',relation,'checksum',False
                for intervention in INTERVENTIONS:
                    for bypass in (False,True):
                        yield family,variant,profile,'integrity-challenge','MR10',intervention,bypass


def one(identity):
    family, variant, profile, cohort, relation, intervention, bypass = identity
    pipeline = OwnedPipeline(profile, intervention, bypass)
    started, cpu = time.perf_counter(), time.process_time()
    with tempfile.TemporaryDirectory(prefix='owned-native-case-') as directory:
        root = Path(directory)
        host = root / 'host.json'
        host.write_text(json.dumps({'family':family,'variant':variant}), encoding='utf-8')
        # Explicitly injected own object-loader interface, not an OS executable
        # invocation, GCC alias, or mocked native result.
        with patch('tosem02.admission.run_host', pipeline.run_host):
            result = evaluate(relation, pipeline, host, root / 'relation',
                              default_compiler='llvmlite', default_optimization=profile)
        direct_started = time.perf_counter()
        direct = direct_integrity(pipeline, KEY1) if relation == 'MR10' else None
        direct_seconds = time.perf_counter() - direct_started
        record = {'identity':list(identity),'verdict':result.verdict,'reason':result.reason,
                  'admission':result.admission,'observations':result.observations,
                  'builds':pipeline.builds,'extractions':pipeline.extractions,'host_calls':pipeline.host_calls,
                  'direct_integrity_verdict':direct,'direct_projection_seconds':direct_seconds}
    # The case timer includes compiler/object/file work, all observations,
    # direct projection and complete private case cleanup, not raw gzip I/O.
    record['case_seconds'] = time.perf_counter() - started
    record['case_cpu_seconds'] = time.process_time() - cpu
    record['host_reference_differences'] = sum(call['native'] != tool.expected(family,variant,call['input'])
                                               for call in pipeline.host_calls)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--small', action='store_true')
    parser.add_argument('--replay', action='store_true')
    args = parser.parse_args()
    started = time.perf_counter()
    if args.replay:
        saved = json.loads((args.out/'summary.json').read_text())
        assert saved['source_versions'] == versions(), 'Saved native source differs'
        args.small = saved['small']
        with gzip.open(args.out/'raw.jsonl.gz', 'rt', encoding='utf-8') as file:
            raw = [json.loads(line) for line in file]
    else:
        args.out.mkdir(parents=True, exist_ok=False)
        raw = []
    actual = []
    output = None if args.replay else gzip.open(args.out/'raw.jsonl.gz', 'wt', encoding='utf-8')
    try:
        for index, identity in enumerate(plan(args.small)):
            record = one(identity)
            if args.replay:
                prior = raw[index]
                def strip_timing(value):
                    if isinstance(value,dict):
                        return {k:strip_timing(v) for k,v in value.items() if not k.endswith('_seconds')}
                    if isinstance(value,list):return [strip_timing(v) for v in value]
                    return value
                assert strip_timing(record) == strip_timing(prior), ('Replay mismatch',identity)
            else:
                output.write(json.dumps(record, separators=(',',':'))+'\n')
            actual.append(record)
            if len(actual) % 64 == 0: print(f'owned native progress {len(actual)}', flush=True)
    finally:
        if output is not None: output.close()
    if args.replay: assert len(raw) == len(actual), 'Saved cohort cardinality differs'
    count = Counter(row['verdict'] for row in actual)
    cohorts = {c:dict(Counter(row['verdict'] for row in actual if row['identity'][3]==c))
               for c in ('clean-workflow','integrity-challenge')}
    llvm = tool.runtime()
    import llvmlite
    summary = {'small':args.small,'source_versions':versions(),'rows':len(actual),'verdicts':dict(count),
        'cohorts':cohorts,'emitted_objects':sum(len(row['builds']) for row in actual),
        'emitted_object_bytes':sum(len(bytes.fromhex(b['object_hex'])) for row in actual for b in row['builds']),
        'native_calls':sum(len(row['host_calls']) + sum(len(b['native_inputs']) for b in row['builds'])
                           for row in actual),
        'host_reference_differences':sum(row['host_reference_differences'] for row in actual),
        'direct_integrity_disagreements':sum(row['verdict']!=row['direct_integrity_verdict'] for row in actual
                                            if row['direct_integrity_verdict'] is not None),
        'case_wall_sum':sum(row['case_seconds'] for row in actual),
        'case_cpu_sum':sum(row['case_cpu_seconds'] for row in actual),
        'activity_wall_seconds':time.perf_counter()-started,
        'environment':{'python':sys.version,'executable':sys.executable,'platform':platform.platform(),
                       'llvmlite':llvmlite.__version__,'llvm':list(llvm.llvm_version_info),
                       'default_triple':llvm.get_default_triple(),'object_format':'ELF64 little-endian ET_REL EM_X86_64',
                       'abi':'Windows AMD64; actual object loaded by MCJIT',
                       'clocks':{name:vars(time.get_clock_info(name)) for name in ('perf_counter','process_time','time')}},
        'scope':'Owned separate implementation/shared WMR2 specification; one data carrier; Windows native object execution, not original Linux executable campaign, production product, security or novelty.'}
    print(json.dumps(summary,indent=2))
    assert cohorts['clean-workflow'] == {'SATISFIED': 20 if args.small else 320}, 'Clean workflow not complete'
    assert not summary['host_reference_differences'] and not summary['direct_integrity_disagreements']
    if not args.replay:
        (args.out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')


if __name__ == '__main__':main()
