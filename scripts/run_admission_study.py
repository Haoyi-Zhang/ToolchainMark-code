#!/usr/bin/env python3
"""Run the evidence-gated protocol without overwriting retained legacy data."""
from __future__ import annotations
import argparse, csv, hashlib, json, os, platform, shutil, subprocess, tempfile, time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from tosem02.admission import evaluate
from tosem02.catalog import artifact_root, load_mutants, load_relations
from tosem02.pipeline import Pipeline


def task(t):
    host, carrier, defect, relation, base = t
    root = Path(base) / Path(host).stem / carrier / defect / relation
    started = time.perf_counter()
    outcome = evaluate(relation, Pipeline(carrier, defect), Path(host), root)
    row = dict(host=Path(host).name, host_sha256=hashlib.sha256(Path(host).read_bytes()).hexdigest(),
               carrier=carrier, defect_id=defect, relation_id=relation,
               verdict=outcome.verdict, exposed=outcome.exposed and defect!='CLEAN',
               reason=outcome.reason, phase=outcome.phase,
               admission_json=json.dumps(outcome.admission,sort_keys=True,separators=(',',':')),
               observations_json=json.dumps(outcome.observations,sort_keys=True,separators=(',',':')),
               duration_seconds=round(time.perf_counter()-started,6))
    shutil.rmtree(root,ignore_errors=True)
    return row


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--workers',type=int,default=4); ap.add_argument('--design-only',action='store_true')
    ap.add_argument('--clean-only',action='store_true'); args=ap.parse_args()
    root=artifact_root(); hosts=sorted((root/'hosts').glob('H*.c'))
    if args.design_only: hosts=hosts[:1]
    defects=['CLEAN'] + ([] if args.clean_only else [m['id'] for m in load_mutants()])
    relations=[r['id'] for r in load_relations()]
    if args.workers < 1 or args.workers > 32: raise SystemExit('workers must be between 1 and 32')
    args.out.parent.mkdir(parents=True,exist_ok=True)
    if args.out.with_suffix('.partial').exists(): raise SystemExit('Refusing to overwrite an incomplete study matrix')
    if args.out.exists(): raise SystemExit('Refusing to overwrite an existing study matrix')
    with tempfile.TemporaryDirectory(prefix='admission-study-') as td:
        tasks=[(str(h),c,d,r,td) for h in hosts for c in ['string','symbol','section'] for d in defects for r in relations]
        tmp=args.out.with_suffix('.partial')
        with tmp.open('w',newline='',encoding='utf-8') as f, ProcessPoolExecutor(max_workers=max(1,args.workers)) as pool:
            writer=None
            for i,row in enumerate(pool.map(task,tasks,chunksize=2),1):
                if writer is None: writer=csv.DictWriter(f,fieldnames=row.keys()); writer.writeheader()
                writer.writerow(row)
                if i%500==0 or i==len(tasks): f.flush(); print(f'{i}/{len(tasks)}',flush=True)
        tmp.replace(args.out)
    print('matrix',args.out.name,'rows',len(tasks),flush=True)

if __name__=='__main__': main()
