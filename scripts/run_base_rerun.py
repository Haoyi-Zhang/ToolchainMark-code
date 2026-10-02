#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os
from pathlib import Path

from tosem02.catalog import artifact_root
from tosem02.cli import environment
from tosem02.derive import derive
from tosem02.runner import run_breadth, run_catalog


def main() -> None:
    ap=argparse.ArgumentParser(description='Historical Boolean protocol only; not the current evidence-gated estimand')
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--workers', type=int, default=min(8, os.cpu_count() or 1))
    args=ap.parse_args()
    root=artifact_root()
    out=args.output
    if out.exists():
        raise SystemExit('Refusing to overwrite existing historical-run output')
    raw=out/'raw'; derived=out/'derived'
    raw.mkdir(parents=True, exist_ok=True)
    run_catalog(raw/'catalog_matrix.csv', workers=args.workers, pilot=False)
    run_catalog(raw/'pilot_matrix.csv', workers=args.workers, pilot=True)
    run_breadth(raw/'breadth_matrix.csv', workers=args.workers)
    summary=derive(raw/'catalog_matrix.csv', raw/'breadth_matrix.csv', raw/'pilot_matrix.csv', derived)
    (out/'environment.json').write_text(json.dumps(environment(),indent=2)+'\n')
    checks={
      'catalog_rows_1050': summary['catalog_rows']==1050,
      'clean_42_of_42': summary['clean_rows']==42 and summary['clean_passes']==42,
      'mutant_rows_1008': summary['mutant_rows']==1008,
      'failing_mutant_rows_248': summary['failing_mutant_rows']==248,
      'defect_units_72_of_72': summary['defect_units']==72 and summary['full_suite_killed']==72,
      'breadth_216_of_216': summary['breadth_rows']==216 and summary['breadth_passes']==216,
      'suite_counts': summary['suite_counts']=={'B0-Roundtrip':21,'B1-Conventional':27,'B2-Differential':33,'Full':72},
      'pilot_65_of_72': summary['pilot']['unit_count']==72 and summary['pilot']['full_suite_killed']==65,
    }
    report={'schema_version':'1.0','classification':'FRESH_SAME_ENVIRONMENT_24_OPERATOR_BASE_MATRIX_RERUN','command':f'python3 scripts/run_base_rerun.py --output {out.as_posix()} --workers {args.workers}','summary':summary,'checks':checks,'verdict':'PASS' if all(checks.values()) else 'FAIL'}
    (out/'recheck_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if report['verdict']!='PASS': raise SystemExit(1)

if __name__=='__main__': main()
