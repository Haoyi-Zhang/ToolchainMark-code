from __future__ import annotations

import argparse
import gzip
import json
import os
import platform
import subprocess
import sys
import tempfile
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


def derive_current_native(root: Path, output: Path) -> None:
    """Rederive canonical current records into a new, external directory.

    Published gzip bytes are unpacked only temporarily. Historical data and
    paper inputs are read-only; no table generator is part of this command.
    """
    output = output.resolve()
    if output.exists():
        raise SystemExit('Refusing to overwrite an existing derivation output')
    if output.is_relative_to(root.parent.resolve()):
        raise SystemExit('Derivation output must be outside the supplied project')
    current = root / 'results/current-native'
    with tempfile.TemporaryDirectory(prefix='tosem02-current-derive-') as temporary:
        temporary = Path(temporary)
        for name in ('first', 'second'):
            data = gzip.decompress((current / (name + '.csv.gz')).read_bytes())
            (temporary / (name + '.csv')).write_bytes(data)
        # Reserve the new destination; failed derivations retain their outputs.
        output.mkdir(parents=True, exist_ok=False)
        subprocess.run([
            sys.executable, str(root / 'scripts/derive_admission_study.py'),
            '--matrix', str(temporary / 'first.csv'),
            '--rerun', str(temporary / 'second.csv'),
            '--mutants', str(root / 'specs/mutants.json'),
            '--legacy', str(root / 'results/raw/robustness_matrix.csv'),
            '--out', str(output),
        ], check=True)


def main() -> None:
    parser=argparse.ArgumentParser(description='Evidence-gated watermark validation; retained Boolean evidence is historical')
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ('run','robustness'):
        p=sub.add_parser(name,help='execute the current evidence-gated protocol into a NEW file')
        p.add_argument('--out','--output',dest='out',type=Path,required=True)
        p.add_argument('--workers',type=int,default=4)
        p.add_argument('--design-only',action='store_true')
        p.add_argument('--clean-only',action='store_true')
    p=sub.add_parser('derive',help='rederive results/current-native/first.csv.gz and second.csv.gz; never write paper inputs')
    p.add_argument('--out','--output',dest='out',type=Path,required=True,
                   help='NEW derivation directory outside the supplied project')
    sub.add_parser('recheck',help='run legacy retained-evidence checks')
    args=parser.parse_args(); root=artifact_root()
    if args.command in ('run','robustness'):
        cmd=[sys.executable,str(root/'scripts/run_admission_study.py'),'--out',str(args.out),'--workers',str(args.workers)]
        if args.design_only:cmd.append('--design-only')
        if args.clean_only:cmd.append('--clean-only')
        subprocess.run(cmd,check=True);return
    if args.command=='derive':
        derive_current_native(root,args.out);return
    report=recheck(root); print(json.dumps(report,indent=2))

if __name__=='__main__':main()
