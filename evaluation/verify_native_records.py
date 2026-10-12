"""Verify published native data without compilers, host execution or network.

The default is read-only, apart from temporary data-only rederivation. Explicit
--paper checks current TeX bindings; --write-paper regenerates only the two
changed TeX inputs. Historical generators and native-triggering paths are not
modified or invoked. This is not another native campaign.
"""
from pathlib import Path
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
    args=parser.parse_args()
    if args.write_paper and args.paper is None: parser.error('--write-paper requires --paper')
    binding=json.loads((DATA/'native-inputs.json').read_text(encoding='utf-8'))
    expected={entry['path'] for entry in binding['native_paths']}
    actual={f.relative_to(ROOT).as_posix() for prefix in ('src','hosts','scripts','specs','tests')
            for f in (ROOT/prefix).rglob('*') if f.is_file() and '__pycache__' not in f.parts and f.suffix!='.pyc'}
    actual.add('.github/workflows/native-compiler-campaign.yml')
    assert actual==expected,'Native input path set changed'
    for entry in binding['native_paths']:
        data=(ROOT/entry['path']).read_bytes()
        digest=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        assert digest==entry['git_blob_sha'], 'Native input changed: '+entry['path']
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
            assert len(packed)==t['compressed_bytes'] and sha(packed)==t['gzip_sha256']
            assert len(unpacked)==t['uncompressed_bytes'] and sha(unpacked)==t['raw_sha256']
            raw.append(unpacked)
            matrices[label+'_'+name]=csv_rows(unpacked)
        first,second=(matrices[label+'_'+name] for name in ('first','second'))
        require_study_coverage(first,second)
        assert derive.matrix_protocol(first)==derive.matrix_protocol(second)=='evidence-gated-v2-checksum-locality'
        assert all(r['verdict']=='INCONSISTENT' for r in first if r['defect_id']=='M16' and r['relation_id']=='MR10')
        with tempfile.TemporaryDirectory(prefix='native-records-') as temporary:
            tmp=Path(temporary)
            for name,data in zip(('first','second'),raw): (tmp/(name+'.csv')).write_bytes(data)
            summary=derive.derive(tmp/'first.csv',ROOT/'specs/mutants.json',tmp/'derived',ROOT/'results/raw/robustness_matrix.csv',tmp/'second.csv')
            assert all(derive.scientific_checks(summary).values())
            assert summary['row_accounting']==summarize_rows(first)
            for downloaded in (base/'derived').iterdir():
                if not downloaded.is_file(): continue
                if downloaded.name=='scientific_checks.json':
                    original=json.loads(downloaded.read_text(encoding='utf-8'))
                    assert original['verdict']=='PASS' and all(original['checks'].values())
                    continue
                rederived=tmp/'derived'/downloaded.name
                if downloaded.suffix=='.json':
                    assert json.loads(downloaded.read_text(encoding='utf-8'))==json.loads(rederived.read_text(encoding='utf-8')),downloaded.name
                else: assert csv_rows(downloaded.read_bytes())==csv_rows(rederived.read_bytes()),downloaded.name
        summaries[label]=summary
    a={key(r):r for r in matrices['canonical_first']}
    b={key(r):r for r in matrices['mirror_first']}
    assert a.keys()==b.keys()
    fields=[f for f in next(iter(a.values())) if f!='duration_seconds']
    assert all(a[k][f]==b[k][f] for k in a for f in fields)
    if args.paper is not None:
        for name,text in paper_inputs(summaries['canonical']).items():
            path=args.paper/'generated'/name
            if args.write_paper and path.read_text(encoding='utf-8')!=text:
                path.write_text(text,encoding='utf-8',newline='\n')
            assert path.read_text(encoding='utf-8')==text,'Current paper input differs: '+name
    print(json.dumps(dict(verdict='PASS',scope='Data-only verification; no native execution and no default paper writes.',
                          applicable_native_runs=[binding['canonical_run'],binding['mirror_run']],
                          unchanged_native_input_files=len(binding['native_paths']),
                          matrix_rows={k:len(v) for k,v in matrices.items()},
                          canonical_mirror_field_comparisons=len(a)*len(fields),
                          paper_checked=args.paper is not None,paper_write_requested=args.write_paper),indent=2))

if __name__=='__main__': main()
