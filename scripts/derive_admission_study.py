#!/usr/bin/env python3
"""Derive admission coverage, conditional sensitivity, and paired evidence.

Unit and row denominators are deliberately separate. An inadmissible relation
cannot count as satisfied or expose a unit. Planned units remain in the overall
sensitivity denominator, so dropping a hard case cannot improve that score.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, math, random, statistics
from collections import Counter,defaultdict
from pathlib import Path

RELATIONS=[f'MR{i:02d}' for i in range(1,15)]
SUITES={'round_trip':['MR01'],'host_semantics':['MR01','MR02'],
        'compiler_differential':['MR01','MR02','MR06','MR07'],'complete_catalog':RELATIONS}
DESIGN='H01-gcd.c'


def rows(path):
    with Path(path).open(newline='',encoding='utf-8') as f:return list(csv.DictReader(f))

def write_csv(path, data):
    data=list(data)
    if not data:return
    with Path(path).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=data[0].keys());w.writeheader();w.writerows(data)

def write_json(path,data):Path(path).write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def key(r):return r['host'],r['carrier'],r['defect_id'],r['relation_id']

def exact_p(b,c):
    n=b+c
    return min(1.0,2*sum(math.comb(n,i) for i in range(min(b,c)+1))/2**n) if n else 1.0

def cover(units,kills,weights=None):
    remaining=set(units);selected=[]
    while remaining:
        scores=[]
        for i,r in enumerate(RELATIONS):
            gain={u for u in remaining if r in kills.get(u,set())}
            count=sum(weights[u] for u in gain) if weights else len(gain)
            scores.append((count,-i,r,gain))
        n,_,r,g=max(scores)
        if n==0:break
        selected.append(r);remaining-=g
    return selected

def derive(matrix, mutants_path, out, legacy=None, rerun=None):
    out.mkdir(parents=True,exist_ok=True); rr=rows(matrix)
    mutants={m['id']:m for m in json.loads(mutants_path.read_text())['mutants']}
    assert len({key(r) for r in rr})==len(rr),'duplicate scientific row identity'
    assert all(r['verdict'] in {'SATISFIED','INCONSISTENT','INADMISSIBLE'} for r in rr)
    for r in rr:
        assert (r['exposed']=='True')==(r['defect_id']!='CLEAN' and r['verdict']=='INCONSISTENT')
        if r['verdict']!='INADMISSIBLE':assert all(json.loads(r['admission_json']).values())
    clean=[r for r in rr if r['defect_id']=='CLEAN']; faulty=[r for r in rr if r['defect_id']!='CLEAN']
    units=sorted({key(r)[:3] for r in faulty});design=[u for u in units if u[0]==DESIGN]
    kills=defaultdict(set);admitted=defaultdict(set)
    for r in faulty:
        u=key(r)[:3]
        if r['verdict']!='INADMISSIBLE':admitted[u].add(r['relation_id'])
        if r['verdict']=='INCONSISTENT':kills[u].add(r['relation_id'])
    byrelation=[]
    for rel in RELATIONS:
        r=[x for x in faulty if x['relation_id']==rel];c=Counter(x['verdict'] for x in r)
        byrelation.append(dict(relation=rel,planned=len(r),admitted=c['SATISFIED']+c['INCONSISTENT'],
                               satisfied=c['SATISFIED'],inconsistent=c['INCONSISTENT'],inadmissible=c['INADMISSIBLE'],
                               design_inconsistent=sum(rel in kills[u] for u in design)))
    write_csv(out/'relation_outcomes.csv',byrelation)
    reasons=Counter(r['reason'] for r in rr if r['verdict']=='INADMISSIBLE')
    write_csv(out/'admission_failures.csv',[dict(reason=k,rows=v) for k,v in sorted(reasons.items())])
    unitrows=[dict(host=u[0],carrier=u[1],defect_id=u[2],fault_class=mutants[u[2]]['fault_class'],
                   admitted_relations=' '.join(sorted(admitted[u])),inconsistent_relations=' '.join(sorted(kills[u])),
                   exposed=bool(kills[u]),direct_relation=mutants[u[2]]['primary_relation'],
                   primary_exclusive=kills[u]=={mutants[u[2]]['primary_relation']}) for u in units]
    write_csv(out/'unit_outcomes.csv',unitrows)
    suite_rows=[]
    for name,rs in SUITES.items():
        active=set(rs)
        suite_rows.append(dict(suite=name,design_units=len(design),design_exposed=sum(bool(kills[u]&active) for u in design),
                               expanded_units=len(units),expanded_exposed=sum(bool(kills[u]&active) for u in units),
                               expanded_units_with_admitted_case=sum(bool(admitted[u]&active) for u in units)))
    write_csv(out/'suites.csv',suite_rows)
    comparisons=[]
    for a,b in [('host_semantics','round_trip'),('compiler_differential','host_semantics'),('complete_catalog','round_trip')]:
        wa,wb=set(SUITES[a]),set(SUITES[b]);better=sum(bool(kills[u]&wa) and not bool(kills[u]&wb) for u in design)
        worse=sum(bool(kills[u]&wb) and not bool(kills[u]&wa) for u in design)
        comparisons.append(dict(suite=a,baseline=b,suite_only=better,baseline_only=worse,exact_two_sided_p=exact_p(better,worse)))
    write_json(out/'paired_comparison.json',comparisons)
    lookup={key(r):r['verdict'] for r in faulty}; non=[r for r in faulty if r['host']!=DESIGN]
    replay=sum(r['verdict']==lookup[(DESIGN,r['carrier'],r['defect_id'],r['relation_id'])] for r in non)
    killset_test=[u for u in units if u[0]!=DESIGN]
    killset_matches=sum(kills[u]==kills[(DESIGN,u[1],u[2])] for u in killset_test)
    classes=sorted({x['fault_class'] for x in mutants.values()}); class_rows=[]
    for c in classes:
        train=[u for u in design if mutants[u[2]]['fault_class']!=c]
        selected=cover(train,kills);test=[u for u in units if u[0]!=DESIGN and mutants[u[2]]['fault_class']==c]
        exposed=sum(bool(kills[u]&set(selected)) for u in test)
        class_rows.append(dict(fault_class=c,selected_relations=' '.join(selected),test_units=len(test),exposed=exposed,sensitivity=exposed/len(test)))
    write_csv(out/'class_holdout.csv',class_rows)
    op_rows=[]
    for m in sorted(mutants):
        selected=cover([u for u in design if u[2]!=m],kills);test=[u for u in units if u[0]!=DESIGN and u[2]==m]
        exposed=sum(bool(kills[u]&set(selected)) for u in test)
        op_rows.append(dict(defect_id=m,selected_relations=' '.join(selected),test_units=len(test),exposed=exposed,sensitivity=exposed/len(test)))
    write_csv(out/'operator_holdout.csv',op_rows)
    carrier_rows=[]
    for c in ['string','symbol','section']:
        selected=cover([u for u in design if u[1]!=c],kills);test=[u for u in units if u[1]==c]
        exposed=sum(bool(kills[u]&set(selected)) for u in test)
        carrier_rows.append(dict(carrier=c,selected_relations=' '.join(selected),test_units=len(test),exposed=exposed,sensitivity=exposed/len(test)))
    write_csv(out/'carrier_holdout.csv',carrier_rows)
    rng=random.Random(20260923);strata=[[u for u in design if mutants[u[2]]['fault_class']==c] for c in classes]
    bootstrap=[]; selections=Counter()
    for replicate in range(10000):
        sampled=[u for st in strata for u in rng.choices(st,k=len(st))];weights=Counter(sampled)
        selected=cover(weights,kills,weights);selections.update(selected);test=[u for u in design if u not in weights]
        exposed=sum(bool(kills[u]&set(selected)) for u in test)
        bootstrap.append(dict(replicate=replicate,suite_size=len(selected),out_of_bag_units=len(test),exposed=exposed,
                              sensitivity=exposed/len(test) if test else '',selected_relations=' '.join(selected)))
    write_csv(out/'bootstrap.csv',bootstrap)
    vals=[r['sensitivity'] for r in bootstrap if r['sensitivity']!='']
    bootstrap_summary=dict(seed=20260923,replicates=10000,nonempty_out_of_bag=len(vals),
                           minimum=min(vals),median=statistics.median(vals),perfect=sum(v==1 for v in vals),
                           suite_size_median=statistics.median(r['suite_size'] for r in bootstrap),selection_counts=dict(selections))
    write_json(out/'bootstrap_summary.json',bootstrap_summary)
    summary=dict(protocol='evidence-gated-v1',rows=len(rr),clean_rows=len(clean),
                 clean=dict(Counter(r['verdict'] for r in clean)),defect_rows=len(faulty),
                 defect_verdicts=dict(Counter(r['verdict'] for r in faulty)),unit_count=len(units),
                 units_exposed=sum(bool(kills[u]) for u in units),units_with_admitted_case=sum(bool(admitted[u]) for u in units),
                 design_units=len(design),design_exposed=sum(bool(kills[u]) for u in design),
                 unrevealed_operators=sorted({u[2] for u in units if not kills[u]}),
                 reasons=dict(reasons),subject_replay=dict(matches=replay,rows=len(non),killsets_equal=killset_matches,killsets=len(killset_test)),
                 direct_exclusive_units=sum(r['primary_exclusive'] for r in unitrows),
                 zero_sensitivity_classes=[r['fault_class'] for r in class_rows if not r['exposed']],
                 zero_sensitivity_operators=[r['defect_id'] for r in op_rows if not r['exposed']],
                 bootstrap=bootstrap_summary,suites=suite_rows,
                 run_timing=dict(median=statistics.median(float(r['duration_seconds']) for r in rr),
                                 maximum=max(float(r['duration_seconds']) for r in rr)),matrix_sha256=sha(matrix))
    if legacy:
        old={key(r):r for r in rows(legacy)}; transitions=Counter()
        for r in rr:
            k=key(r)
            if k in old:transitions[('PASS' if old[k]['pass']=='True' else 'FAIL',r['verdict'])]+=1
        summary['legacy_transitions']=[dict(legacy=a,evidence_gated=b,rows=n) for (a,b),n in sorted(transitions.items())]
        write_csv(out/'legacy_transitions.csv',summary['legacy_transitions'])
    if rerun:
        other=rows(rerun); d={key(r):r for r in other}; diff=[]; fields=[f for f in rr[0] if f!='duration_seconds']
        assert len(d)==len(other),'rerun duplicate keys'
        for r in rr:
            q=d.get(key(r))
            for f in fields:
                if q is None or q[f]!=r[f]:diff.append(dict(key=key(r),field=f))
        report=dict(rows=len(rr),rerun_rows=len(other),identical_key_sets=set(d)=={key(r) for r in rr},
                    compared_fields=fields,field_comparisons=len(rr)*len(fields),differences=len(diff),examples=diff[:20],
                    all_durations_positive=all(float(r['duration_seconds'])>0 for r in rr+other),
                    first_sha256=sha(matrix),second_sha256=sha(rerun))
        report['verdict']='PASS' if not diff and report['identical_key_sets'] and report['all_durations_positive'] else 'FAIL'
        write_json(out/'rerun_comparison.json',report);summary['rerun']=report
    write_json(out/'summary.json',summary)
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--matrix',type=Path,required=True);p.add_argument('--mutants',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--legacy',type=Path);p.add_argument('--rerun',type=Path)
    a=p.parse_args();s=derive(a.matrix,a.mutants,a.out,a.legacy,a.rerun);print(json.dumps(s,indent=2))
