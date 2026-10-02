#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, hashlib, json, statistics
from pathlib import Path

KEY = ['surface','host','host_sha256','carrier','defect_id','defect_operator','fault_class','relation_id','relation_name','polarity','pilot']
IGNORE = {'duration_seconds'}

def read(path: Path) -> list[dict[str,str]]:
    with path.open(newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument('first',type=Path); parser.add_argument('second',type=Path); parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    one,two=read(args.first),read(args.second)
    def index(rows):
        result={}; duplicates=0
        for row in rows:
            key=tuple(row[field] for field in KEY)
            duplicates += key in result
            result[key]=row
        return result,duplicates
    first,dup_first=index(one); second,dup_second=index(two)
    missing_first=sorted(set(second)-set(first)); missing_second=sorted(set(first)-set(second))
    fields=[field for field in one[0] if field not in IGNORE]
    differences=[]; comparisons=0; difference_count=0
    for key in sorted(set(first)&set(second)):
        for field in fields:
            comparisons += 1
            if first[key][field] != second[key][field]:
                difference_count += 1
                if len(differences)<20:
                    differences.append({'key':key,'field':field,'first':first[key][field],'second':second[key][field]})
    timing_first=[float(row['duration_seconds']) for row in one]
    timing_second=[float(row['duration_seconds']) for row in two]
    report={
      'schema_version':'1.0',
      'comparison':'two complete 18-subject robustness executions under an identical frozen protocol',
      'first_run':{'path':str(args.first),'rows':len(one),'sha256':sha(args.first)},
      'second_run':{'path':str(args.second),'rows':len(two),'sha256':sha(args.second)},
      'row_key_fields':KEY,
      'ignored_nondeterministic_fields':sorted(IGNORE),
      'duplicate_keys_first':dup_first,'duplicate_keys_second':dup_second,
      'key_sets_identical':not missing_first and not missing_second,
      'missing_from_first':len(missing_first),'missing_from_second':len(missing_second),
      'compared_rows':len(set(first)&set(second)),
      'compared_non_timing_fields_per_row':len(fields),
      'non_timing_field_comparisons':comparisons,
      'non_timing_differences':difference_count,
      'sample_differences':differences,
      'sample_missing_from_first':missing_first[:10],
      'sample_missing_from_second':missing_second[:10],
      'timing':{
        'first':{'all_positive':all(x>0 for x in timing_first),'median_seconds':statistics.median(timing_first),'max_seconds':max(timing_first),'sum_seconds':sum(timing_first)},
        'second':{'all_positive':all(x>0 for x in timing_second),'median_seconds':statistics.median(timing_second),'max_seconds':max(timing_second),'sum_seconds':sum(timing_second)},
      },
    }
    report['verdict']='PASS' if report['key_sets_identical'] and not dup_first and not dup_second and difference_count==0 else 'FAIL'
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    raise SystemExit(0 if report['verdict']=='PASS' else 1)

if __name__=='__main__': main()
