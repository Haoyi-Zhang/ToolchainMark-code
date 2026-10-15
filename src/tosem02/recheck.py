"""Current publication and retained-evidence checks; no native execution."""
from __future__ import annotations
import hashlib
import importlib.util
from pathlib import Path


def package_checker():
    source=Path(__file__).resolve().parents[2]/'scripts/verify_package.py'
    spec=importlib.util.spec_from_file_location('tosem02_review_entry',source)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_paper_entry(project:Path):
    return package_checker().check_review_entry(project)


def check_review_pdf_bindings(paper:Path,visual:dict)->bool:
    try:
        return all(visual['pdfs'][name]['sha256']==hashlib.sha256((paper/(name+'.pdf')).read_bytes()).hexdigest()
                   for name in ('main','online-supplement'))
    except (OSError,KeyError,TypeError):
        return False


def recheck(artifact:Path)->dict:
    """Use the current full package checker and propagate every failed gate."""
    result=package_checker().audit_project(artifact.resolve().parent)
    if result.get('verdict')!='PASS':
        failed=[name for name,passed in result.get('checks',{}).items() if not passed]
        raise RuntimeError('Evidence checks failed: '+', '.join(failed))
    return result
