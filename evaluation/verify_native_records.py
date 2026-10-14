"""Verify published native data without compilers, host execution or network.

The default is read-only, apart from temporary data-only rederivation. Explicit
--paper checks current TeX bindings; --write-paper regenerates only the two
changed TeX inputs. Historical generators and native-triggering paths are not
modified or invoked. This is not another native campaign.
"""
from pathlib import Path, PurePosixPath
import argparse
import csv
import gzip
import hashlib
import importlib.util
import io
import json
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'results/current-native'
sys.path.insert(0,str(ROOT/'src'))
from tosem02.study_coverage import require_study_coverage
from tosem02.accounting import summarize_rows

def sha(data): return hashlib.sha256(data).hexdigest()
def csv_rows(data): return list(csv.DictReader(io.StringIO(data.decode('utf-8'),newline='')))
def key(row): return tuple(row[k] for k in ('host','carrier','defect_id','relation_id'))

def require(condition, message):
    if not condition:
        raise ValueError(message)

def git_blob(path):
    data=path.read_bytes()
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()

def native_paths(root):
    paths={f.relative_to(root).as_posix() for prefix in ('src','hosts','scripts','specs','tests')
           for f in (root/prefix).rglob('*') if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc'}
    if (root/'.github/workflows/native-compiler-campaign.yml').is_file():
        paths.add('.github/workflows/native-compiler-campaign.yml')
    return paths

def verify_native_source_binding(binding, current_root=ROOT, data_root=DATA, source_root=None):
    """Verify historical bytes, without claiming that current code executed old runs."""
    entries=binding['native_paths']
    expected={entry['path'] for entry in entries}
    require(len(entries)==len(expected)==71, 'Historical native manifest must contain 71 unique paths')
    for entry in entries:
        path=PurePosixPath(entry['path'])
        require(not path.is_absolute() and '..' not in path.parts and
                (path.parts[0] in {'src','hosts','scripts','specs','tests'} or
                 entry['path']=='.github/workflows/native-compiler-campaign.yml'),
                'Unsafe native input path: '+entry['path'])
    if source_root is not None:
        actual=native_paths(source_root)
        require(actual==expected, 'Explicit preserved v2 root has a different native input path set')
        for entry in entries:
            path=entry['path']
            require(git_blob(source_root/path)==entry['git_blob_sha'], 'Historical native input changed: '+path)
        return dict(historical_native_input_files=len(entries),current_identical_files=None,
                    original_snapshot_files_used=0,later_recovered_files_used=0,
                    current_diverged_paths=[],current_only_paths=[],
                    source_binding='explicit-preserved-v2-root')

    provenance=json.loads((data_root/'provenance.json').read_text(encoding='utf-8'))
    snapshot_entries=provenance['source_snapshot']['files']
    snapshot={entry['path']:entry['git_blob_sha'] for entry in snapshot_entries}
    require(len(snapshot)==len(snapshot_entries)==23 and set(snapshot)<=expected,
            'Original source-snapshot declaration changed')
    recovery=json.loads((data_root/'historical-source-recovery.json').read_text(encoding='utf-8'))
    require(recovery['repository']==provenance['canonical']['repository'],
            'Recovered source repository differs from historical canonical repository')
    require(recovery['head_sha']==binding['canonical_head'], 'Recovered source head differs from historical canonical head')
    require(recovery['mirror_repository']==provenance['mirror']['repository'] and
            recovery['mirror_head_sha']==binding['mirror_head'],
            'Recovered source mirror identity differs from historical manifest')
    recovery_entries=recovery['files']
    recovered={entry['path']:entry['git_blob_sha'] for entry in recovery_entries}
    require(len(recovered)==len(recovery_entries) and set(recovered)<=expected and not (set(recovered)&set(snapshot)),
            'Recovered source declaration overlaps or duplicates historical inputs')
    for label,declared,base in (('Original snapshot',snapshot,data_root/'source-snapshot'),
                                ('Later recovery',recovered,data_root/'historical-source-recovery')):
        for path,digest in declared.items():
            require(digest==next(entry['git_blob_sha'] for entry in entries if entry['path']==path),
                    label+' declaration differs from historical manifest: '+path)
            require((base/path).is_file() and git_blob(base/path)==digest,
                    label+' bytes differ from historical manifest: '+path)

    identical=0; snapshot_used=0; recovered_used=0; diverged=[]
    for entry in entries:
        path=entry['path']; current=current_root/path
        if current.is_file() and git_blob(current)==entry['git_blob_sha']:
            identical+=1
        elif path in snapshot:
            snapshot_used+=1; diverged.append(path)
        elif path in recovered:
            recovered_used+=1; diverged.append(path)
        else:
            raise ValueError('Historical native input bytes unavailable: '+path)
    require(identical+snapshot_used+recovered_used==71, 'Historical input binding incomplete')
    return dict(historical_native_input_files=len(entries),current_identical_files=identical,
                original_snapshot_files_used=snapshot_used,later_recovered_files_used=recovered_used,
                current_diverged_paths=diverged,
                current_only_paths=sorted(native_paths(current_root)-expected),
                source_binding='historical-71-byte-verified-mixed-sources')

def paper_inputs(summary):
    n=lambda v:f'{v:,}'
    a=summary['row_accounting']
    macro={
        'EvidenceRows':n(summary['rows']),'EvidenceClean':n(summary['clean_rows']),
        'EvidenceNoncleanRows':n(summary['defect_rows']),
        'EvidenceStageIsolationRows':n(a['stage_isolation_rows']),
        'EvidenceFaultRows':n(a['fault_active_rows']),
        'EvidenceInconsistent':n(summary['defect_verdicts']['INCONSISTENT']),
        'EvidenceInadmissible':n(summary['defect_verdicts']['INADMISSIBLE']),
        'EvidenceFaultSatisfied':n(a['verdicts_by_activation']['FAULT_ACTIVE']['SATISFIED']),
        'EvidenceExposed':n(summary['units_exposed']),'EvidenceDesignExposed':str(summary['design_exposed']),
        'EvidenceExclusive':n(summary['direct_exclusive_units']),
        'EvidenceReplay':n(summary['subject_replay']['matches']),
        'EvidenceKillsets':n(summary['subject_replay']['killsets_equal']),
        'EvidenceZeroClasses':str(len(summary['zero_sensitivity_classes'])),
        'EvidenceZeroOperators':str(len(summary['zero_sensitivity_operators'])),
        'EvidenceBootstrapSize':str(int(summary['bootstrap']['suite_size_median'])),
        'EvidenceBootstrapPerfect':n(summary['bootstrap']['perfect']),
        'EvidenceBootstrapMin':f"{100*summary['bootstrap']['minimum']:.1f}\\%",
        'EvidenceMedianSeconds':f"{summary['run_timing']['median']:.3f}",
        'EvidenceComparisonStatement':f"The two current complete runs agree on all {n(summary['rerun']['rows'])} scientific row keys and {n(summary['rerun']['field_comparisons'])} comparisons over 11 stored non-timing fields; complete request, action, command, artifact, and per-input trajectories were not retained.",
    }
    macros='% Derived from artifact/results/current-native/derived; do not edit by hand.\n'
    macros+=''.join('\\newcommand{\\'+k+'}{'+v+'}\n' for k,v in macro.items())
    table=('\\begin{table}[t]\n\\caption{Three-valued outcomes of the current checksum-locality protocol. An inadmissible case contributes to the attempted denominator but never to a fault-exposure numerator.}\n'
           '\\label{tab:admission-overview}\n\\small\n\\begin{tabularx}{\\textwidth}{@{}X r r r r@{}}\n\\toprule\nSurface & Attempted & Satisfied & Inconsistent & Inadmissible \\\\\n\\midrule\n')
    rows=[['Clean',n(summary['clean_rows']),n(summary['clean']['SATISFIED']),0,0],
          ['Stage isolation',macro['EvidenceStageIsolationRows'],macro['EvidenceStageIsolationRows'],0,0],
          ['Fault-active mechanisms',macro['EvidenceFaultRows'],macro['EvidenceFaultSatisfied'],macro['EvidenceInconsistent'],macro['EvidenceInadmissible']],
          ['Total',macro['EvidenceRows'],n(summary['clean_rows']+summary['defect_verdicts']['SATISFIED']),macro['EvidenceInconsistent'],macro['EvidenceInadmissible']]]
    table+=''.join(' & '.join(str(x) for x in row)+' \\\\\n' for row in rows)
    table+='\\bottomrule\n\\end{tabularx}\n\\end{table}\n'
    return {'admission-results.tex':macros,'admission-overview.tex':table}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--paper',type=Path,help='Optional paper directory; checks only, unless --write-paper is explicit')
    parser.add_argument('--write-paper',action='store_true')
    parser.add_argument('--source-root',type=Path,
                        help='Explicit preserved v2 input root for historical-source binding; does not certify current code')
    args=parser.parse_args()
    if args.write_paper and args.paper is None: parser.error('--write-paper requires --paper')
    binding=json.loads((DATA/'native-inputs.json').read_text(encoding='utf-8'))
    source=verify_native_source_binding(binding,source_root=args.source_root.resolve() if args.source_root else None)
    spec=importlib.util.spec_from_file_location('native_data_derive',ROOT/'scripts/derive_admission_study.py')
    derive=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(derive)
    transport=json.loads((DATA/'transport.json').read_text(encoding='utf-8'))
    matrices={}
    summaries={}
    for label,base in [('canonical',DATA),('mirror',DATA/'mirror')]:
        raw=[]
        for name in ('first','second'):
            packed=(base/(name+'.csv.gz')).read_bytes()
            unpacked=gzip.decompress(packed)
            t=transport[label+'_'+name]
            require(len(packed)==t['compressed_bytes'] and sha(packed)==t['gzip_sha256'],
                    'Compressed native matrix differs from transport manifest: '+label+'/'+name)
            require(len(unpacked)==t['uncompressed_bytes'] and sha(unpacked)==t['raw_sha256'],
                    'Raw native matrix differs from transport manifest: '+label+'/'+name)
            raw.append(unpacked)
            matrices[label+'_'+name]=csv_rows(unpacked)
        first,second=(matrices[label+'_'+name] for name in ('first','second'))
        require_study_coverage(first,second)
        for name,rows in (('first',first),('second',second)):
            require(all(row['verdict'] in {'SATISFIED','INCONSISTENT','INADMISSIBLE'} for row in rows),
                    'Invalid native verdict: '+label+'/'+name)
            require(all((row['exposed']=='True')==
                        (row['defect_id']!='CLEAN' and row['verdict']=='INCONSISTENT') for row in rows),
                    'Native exposure/verdict mismatch: '+label+'/'+name)
            require(all(all(json.loads(row['admission_json']).values()) for row in rows
                        if row['verdict']!='INADMISSIBLE'),
                    'Admitted native row has a failed admission fact: '+label+'/'+name)
        require(derive.matrix_protocol(first)==derive.matrix_protocol(second)=='evidence-gated-v2-checksum-locality',
                'Retained MR10 protocol differs: '+label)
        m16_mr10=[r for r in first if r['defect_id']=='M16' and r['relation_id']=='MR10']
        require(len(m16_mr10)==54 and all(r['verdict']=='INCONSISTENT' for r in m16_mr10),
                'M16/MR10 retained verdict differs: '+label)
        with tempfile.TemporaryDirectory(prefix='native-records-') as temporary:
            tmp=Path(temporary)
            for name,data in zip(('first','second'),raw): (tmp/(name+'.csv')).write_bytes(data)
            summary=derive.derive(tmp/'first.csv',ROOT/'specs/mutants.json',tmp/'derived',ROOT/'results/raw/robustness_matrix.csv',tmp/'second.csv')
            require(all(derive.scientific_checks(summary).values()), 'Rederived scientific gate failed: '+label)
            require(summary['row_accounting']==summarize_rows(first), 'Rederived row accounting differs: '+label)
            for downloaded in (base/'derived').iterdir():
                if not downloaded.is_file(): continue
                if downloaded.name=='scientific_checks.json':
                    original=json.loads(downloaded.read_text(encoding='utf-8'))
                    require(original['verdict']=='PASS' and all(original['checks'].values()),
                            'Downloaded scientific gate is not PASS: '+label)
                    continue
                rederived=tmp/'derived'/downloaded.name
                if downloaded.suffix=='.json':
                    require(json.loads(downloaded.read_text(encoding='utf-8'))==json.loads(rederived.read_text(encoding='utf-8')),
                            'Rederived JSON differs: '+label+'/'+downloaded.name)
                else:
                    require(csv_rows(downloaded.read_bytes())==csv_rows(rederived.read_bytes()),
                            'Rederived CSV differs: '+label+'/'+downloaded.name)
        summaries[label]=summary
    a={key(r):r for r in matrices['canonical_first']}
    b={key(r):r for r in matrices['mirror_first']}
    require(a.keys()==b.keys(), 'Canonical and mirror first-matrix key sets differ')
    fields=[f for f in next(iter(a.values())) if f!='duration_seconds']
    require(all(a[k][f]==b[k][f] for k in a for f in fields),
            'Canonical and mirror first-matrix non-timing fields differ')
    if args.paper is not None:
        for name,text in paper_inputs(summaries['canonical']).items():
            path=args.paper/'generated'/name
            if args.write_paper and path.read_text(encoding='utf-8')!=text:
                path.write_text(text,encoding='utf-8',newline='\n')
            require(path.read_text(encoding='utf-8')==text, 'Current paper input differs: '+name)
    print(json.dumps(dict(verdict='PASS',scope='Data-only verification; no native execution and no default paper writes.',
                          applicable_native_runs=[binding['canonical_run'],binding['mirror_run']],
                          historical_source=source,
                          rederivation_source='current-artifact/scripts/derive_admission_study.py',
                          certifies_v3_native_execution=False,
                          matrix_rows={k:len(v) for k,v in matrices.items()},
                          canonical_mirror_field_comparisons=len(a)*len(fields),
                          paper_checked=args.paper is not None,paper_write_requested=args.write_paper),indent=2))

if __name__=='__main__': main()
