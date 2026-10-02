#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,os,re,stat,sys
from pathlib import Path

def sha(path:Path)->str:
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('project_root',nargs='?',type=Path);ap.add_argument('--write-audit',action='store_true');args=ap.parse_args()
 artifact=Path(__file__).resolve().parents[1];root=(args.project_root or artifact.parent).resolve();audit_path=artifact/'audit/package_audit.json';manifest=artifact/'audit/project_manifest.csv'
 checks={};details={}
 checks['root_entries_exact']=sorted(p.name for p in root.iterdir())==["README.md", "artifact", "paper"]
 files=sorted(p for p in root.rglob('*') if p.is_file());dirs=sorted(p for p in root.rglob('*') if p.is_dir())
 checks['no_symlinks']=not any(p.is_symlink() for p in root.rglob('*'))
 inode={}
 for p in files:inode.setdefault((p.stat().st_dev,p.stat().st_ino),[]).append(p)
 checks['no_shared_hardlinks']=not any(len(v)>1 for v in inode.values())
 forbidden=[]
 for p in root.rglob('*'):
  if p.name in {'.git','__pycache__'} or p.suffix in {'.pyc','.pyo','.aux','.log','.out','.blg','.toc','.synctex.gz','.bak'} or p.name.endswith('~') or (p.is_file() and p.suffix in {'.zip','.tar','.gz'}):forbidden.append(str(p.relative_to(root)))
 checks['no_cache_aux_backup_archive_debris']=not forbidden
 # Text hygiene excludes third-party template/license content and raw scientific data.
 private=[];prompt=[]
 for p in files:
  if p.suffix.lower() not in {'.md','.tex','.py','.sh','.json','.csv','.toml','.txt','.yaml','.yml','.c','.h','.bib'}:continue
  if p.name in {'acmart.cls','ACM-Reference-Format.bst','ACM-LICENSE.txt'}:continue
  try:text=p.read_text(errors='ignore')
  except Exception:continue
  if re.search(r'/mnt/data|/home/oai|sandbox:',text,re.I):private.append(str(p.relative_to(root)))
  if re.search(r'chatgpt|openai|system prompt|chain of thought|assistant response|private prompt',text,re.I):prompt.append(str(p.relative_to(root)))
 checks['no_private_runtime_paths']=not private
 checks['no_prompt_or_model_process_trace']=not prompt
 # Manifest verification.
 manifest_rows=[]
 if manifest.exists():
  with manifest.open(newline='',encoding='utf-8') as f:manifest_rows=list(csv.DictReader(f))
 expected=sorted(p for p in files if p!=manifest)
 checks['manifest_covers_every_file_except_itself']=len(manifest_rows)==len(expected) and {r['path'] for r in manifest_rows}=={p.relative_to(root).as_posix() for p in expected}
 mism=[]
 by={r['path']:r for r in manifest_rows}
 for p in expected:
  rel=p.relative_to(root).as_posix();r=by.get(rel,{})
  if r.get('sha256')!=sha(p) or int(r.get('bytes','-1'))!=p.stat().st_size or r.get('mode')!=f'{stat.S_IMODE(p.stat().st_mode):04o}':mism.append(rel)
 checks['manifest_hash_size_mode_match']=not mism
 # Audits.
 required={
  'science':artifact/'audit/science_verification.json','repair':artifact/'audit/repair_requirements_audit.json','protocol':artifact/'audit/protocol_alignment_audit.json','recompute':artifact/'audit/affected_results_recomputation.json','recheck':artifact/'audit/recheck_report.json',
  'paper_consistency':root/'paper/manuscript_consistency_audit.json','visual':root/'paper/visual_qa.json','page_fit':root/'paper/page_fit_audit.json','font':root/'paper/font_audit.json','rebuild':root/'paper/package_rebuild_audit.json','references':root/'paper/reference_verification_audit.json','citation_shape':root/'paper/citation_shape_audit.json',
 }
 audit_values={}
 for name,p in required.items():
  try:d=json.loads(p.read_text());audit_values[name]=d.get('verdict');checks[f'{name}_audit_pass']=d.get('verdict')=='PASS'
  except Exception:checks[f'{name}_audit_pass']=False
 # Portable scripts.
 science=(artifact/'scripts/verify_science.sh').read_text();optional=(artifact/'scripts/build_paper_optional.sh').read_text();verify=(artifact/'scripts/verify.sh').read_text()
 checks['science_verifier_has_no_paper_dependency']='paper' not in science.lower() and 'author' not in science.lower() and 'history' not in science.lower()
 checks['verify_defaults_to_science_only']='verify_science.sh' in verify and 'verify_package.py' not in verify
 checks['paper_build_is_optional_and_portable']='SKIP: optional paper source is not present' in optional and 'TOSEM-02/../paper' not in optional
 details={'project_files_including_manifest':len(files),'project_directories_including_root':len(dirs)+1,'manifest_rows':len(manifest_rows),'forbidden':forbidden,'private_paths':private,'prompt_traces':prompt,'manifest_mismatches':mism,'audit_verdicts':audit_values}
 result={'schema_version':'2.0','project_root':str(root),'checks':checks,'details':details,'verdict':'PASS' if all(checks.values()) else 'FAIL'}
 if args.write_audit:audit_path.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2))
 return 0 if result['verdict']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
