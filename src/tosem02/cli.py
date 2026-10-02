from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from .catalog import artifact_root
from .derive import derive, write_manifest
from .recheck import recheck
from .runner import run_breadth, run_catalog, run_robustness


def environment() -> dict:
    def first(command: list[str]) -> str:
        proc = subprocess.run(command, text=True, capture_output=True)
        return (proc.stdout or proc.stderr).splitlines()[0] if (proc.stdout or proc.stderr) else ''
    return {
        'python': sys.version.split()[0], 'platform': platform.platform(),
        'gcc': first(['gcc', '--version']), 'clang': first(['clang', '--version']),
        'objcopy': first(['objcopy', '--version']), 'nm': first(['nm', '--version']), 'strip': first(['strip', '--version']),
        'executables': {name: f'PATH:{name}' for name in ['python3', 'gcc', 'clang', 'objcopy', 'nm', 'strip']},
        'path_recording_policy': 'Command names are recorded; machine-local absolute executable paths are intentionally omitted.',
    }


def main() -> None:
    parser=argparse.ArgumentParser(description='Evidence-gated watermark validation; retained Boolean evidence is historical')
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('run','robustness'):
        p=sub.add_parser(name,help='execute the current evidence-gated protocol into a NEW file')
        p.add_argument('--out','--output',dest='out',type=Path,required=True)
        p.add_argument('--workers',type=int,default=4)
        p.add_argument('--design-only',action='store_true')
        p.add_argument('--clean-only',action='store_true')
    sub.add_parser('derive',help='rederive the current gated matrix; preserve all raw evidence')
    sub.add_parser('recheck',help='verify current evidence, identifiers, and draft authorship state')
    args=parser.parse_args(); root=artifact_root()
    if args.command in ('run','robustness'):
        cmd=[sys.executable,str(root/'scripts/run_admission_study.py'),'--out',str(args.out),'--workers',str(args.workers)]
        if args.design_only:cmd.append('--design-only')
        if args.clean_only:cmd.append('--clean-only')
        subprocess.run(cmd,check=True);return
    if args.command=='derive':
        subprocess.run([sys.executable,str(root/'scripts/derive_admission_study.py'),'--matrix',str(root/'results/admission-study/matrix.csv'),'--mutants',str(root/'specs/mutants.json'),'--out',str(root/'results/admission-study/derived'),'--legacy',str(root/'results/raw/robustness_matrix.csv'),'--rerun',str(root/'results/admission-study/rerun.csv')],check=True)
        subprocess.run([sys.executable,str(root/'scripts/generate_admission_tables.py')],check=True);return
    report=recheck(root); print(json.dumps(report,indent=2))

if __name__=='__main__':main()
