#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,shutil,subprocess,tempfile,time
from pathlib import Path
from tosem02.model import BuildRequest,ExtractionError
from tosem02.pipeline import Pipeline,run_host
from tosem02.relations import PAYLOAD1,KEY1,INPUTS

CARRIERS=['string','symbol','section']
OPS=[
 ('relocate','preserve',None),
 ('gnu_debug_strip','preserve',['strip','--strip-debug']),
 ('llvm_debug_strip','preserve',['llvm-objcopy','--strip-debug']),
 ('gnu_full_strip','carrier',['strip','--strip-all']),
 ('llvm_full_strip','carrier',['llvm-objcopy','--strip-all']),
 ('gnu_section_remove','section',['objcopy','--remove-section','.wmrec']),
 ('llvm_section_remove','section',['llvm-objcopy','--remove-section','.wmrec']),
]

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def expected(mode,carrier):
 if mode=='preserve': return 'preserve'
 if mode=='carrier': return 'reject' if carrier=='symbol' else 'preserve'
 if mode=='section': return 'reject' if carrier=='section' else 'preserve'
 raise ValueError(mode)

def classify_observation(expected_outcome, return_code, *, payload_equal=False,
                         host_outputs_equal=False, error_kind='', exception_class=''):
 """Pure verdict boundary: observation failures are not domain rejection."""
 if expected_outcome not in {'preserve','reject'}:
  raise ValueError('unknown expected outcome')
 domain_errors={'absent','wrong-key','checksum','malformed','version'}
 if return_code!=0 or exception_class or (error_kind and error_kind not in domain_errors):
  return 'infrastructure_failure',False
 if error_kind:
  observed='reject' if error_kind=='absent' else 'changed'
 else:
  observed='preserve' if payload_equal and host_outputs_equal else 'changed'
 return observed,observed==expected_outcome

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--output',type=Path,required=True); ap.add_argument('--work-root',type=Path); a=ap.parse_args()
 root=Path(__file__).resolve().parents[1]
 hosts=sorted((root/'hosts').glob('H*.c'))
 work=a.work_root or Path(tempfile.mkdtemp(prefix='tosem02-adverse-'))
 rows=[]
 try:
  for host in hosts:
   for carrier in CARRIERS:
    case=work/host.stem/carrier
    pipe=Pipeline(carrier,'CLEAN')
    build=pipe.build(BuildRequest(host,PAYLOAD1,KEY1,'gcc','O2',case/'build',True,False))
    source_outputs=[run_host(build.binary,v) for v in INPUTS]
    source_payload=pipe.extract(build.binary,KEY1)
    for opname,mode,command in OPS:
     started=time.perf_counter(); target_dir=case/opname; target_dir.mkdir(parents=True,exist_ok=True)
     target=target_dir/'artifact.bin'; shutil.copy2(build.binary,target)
     exp=expected(mode,carrier)
     return_code=0; stderr=''; payload_hex=''; payload_equal=False
     output_equal=False; error_kind=''; exception_class=''
     try:
      if command:
       proc=subprocess.run(command+[str(target)],text=True,capture_output=True,timeout=20)
       return_code=proc.returncode; stderr=proc.stderr.strip()
     except Exception as exc:
      return_code=None; exception_class=type(exc).__name__; stderr=str(exc)
     if return_code==0:
      try:
       value=pipe.extract(target,KEY1); payload_hex=value.hex(); payload_equal=value==source_payload
       if exp=='preserve':
        outputs=[run_host(target,v) for v in INPUTS]; output_equal=outputs==source_outputs
      except ExtractionError as exc:
       error_kind=exc.kind
      except Exception as exc:
       exception_class=type(exc).__name__; stderr=(stderr+' | '+str(exc)).strip(' |')
     observed,passed=classify_observation(exp,return_code,payload_equal=payload_equal,
         host_outputs_equal=output_equal,error_kind=error_kind,exception_class=exception_class)
     rows.append({'host':host.name,'host_sha256':sha(host),'carrier':carrier,'operation':opname,'utility':' '.join(command or ['copy']),
                  'expected':exp,'observed':observed,'pass':passed,'return_code':return_code,'error_kind':error_kind,
                  'payload_hex':payload_hex,'host_outputs_equal':output_equal,'binary_sha256':sha(target),'duration_seconds':round(time.perf_counter()-started,6),
                  'exception_class':exception_class,'stderr':stderr[:500]})
  a.output.parent.mkdir(parents=True,exist_ok=True)
  fields=list(rows[0]);
  with a.output.open('w',newline='') as h:
   w=csv.DictWriter(h,fieldnames=fields);w.writeheader();w.writerows(rows)
  summary={'schema_version':'2.0','rows':len(rows),'passes':sum(r['pass'] for r in rows),
           'violations':sum(not r['pass'] and r['observed']!='infrastructure_failure' for r in rows),
           'infrastructure_failures':sum(r['observed']=='infrastructure_failure' for r in rows),
           'violations_by_operation':{},'violations_by_carrier':{},'all_durations_positive':all(r['duration_seconds']>0 for r in rows)}
  for r in rows:
   if not r['pass'] and r['observed']!='infrastructure_failure':
    summary['violations_by_operation'][r['operation']]=summary['violations_by_operation'].get(r['operation'],0)+1
    summary['violations_by_carrier'][r['carrier']]=summary['violations_by_carrier'].get(r['carrier'],0)+1
  a.output.with_suffix('.summary.json').write_text(json.dumps(summary,indent=2)+"\n")
  print(json.dumps(summary,indent=2))
 finally:
  if a.work_root is None: shutil.rmtree(work,ignore_errors=True)
if __name__=='__main__': main()
