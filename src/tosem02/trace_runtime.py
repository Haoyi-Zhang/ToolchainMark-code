from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import dataclasses
import functools
import hashlib
import inspect
import json
import os
import subprocess
from typing import Any, Iterator

_CURRENT: ContextVar['TraceRecorder | None']=ContextVar('tosem02_trace', default=None)
_ORIGINAL_RUN=subprocess.run


def _sha(path: Path) -> str | None:
    if not path.is_file(): return None
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()


def _normal(value: Any, work: str | None) -> Any:
    if isinstance(value, Path):
        text=str(value)
        if work and text.startswith(work): text='<WORK>'+text[len(work):]
        return text
    if isinstance(value, os.PathLike): return _normal(Path(value),work)
    if isinstance(value, bytes): return {'bytes':len(value),'hex':value.hex() if len(value) <= 64 else None,'sha256':hashlib.sha256(value).hexdigest()}
    if dataclasses.is_dataclass(value): return _normal(dataclasses.asdict(value),work)
    if isinstance(value, dict): return {str(k):_normal(v,work) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [_normal(v,work) for v in value]
    if isinstance(value,(str,int,float,bool)) or value is None: return value
    if hasattr(value,'__dict__'):
        return {k:_normal(v,work) for k,v in vars(value).items() if not k.startswith('_')}
    return repr(value)


class TraceRecorder:
    def __init__(self, task: dict[str, Any]):
        self.task=dict(task); self.work=str(task.get('work') or task.get('work_root') or '')
        self.actions=[]; self.commands=[]; self.artifacts=[]

    def action(self, phase: str, name: str, args: Any=None, result: Any=None, error: str | None=None):
        self.actions.append({'phase':phase,'name':name,'args':_normal(args,self.work),'result':_normal(result,self.work),'error':error})

    def command(self, args: Any, cwd: Any, completed: Any, before: dict[str,str|None], after: dict[str,str|None]):
        self.commands.append({
            'argv':_normal(list(args) if isinstance(args,(list,tuple)) else args,self.work),
            'cwd':_normal(Path(cwd) if cwd else None,self.work),
            'returncode':getattr(completed,'returncode',None),
            'stdout_sha256':hashlib.sha256((getattr(completed,'stdout','') or '').encode()).hexdigest() if isinstance(getattr(completed,'stdout',''),str) else None,
            'stderr_sha256':hashlib.sha256((getattr(completed,'stderr','') or '').encode()).hexdigest() if isinstance(getattr(completed,'stderr',''),str) else None,
            'input_output_hashes_before':before,
            'input_output_hashes_after':after,
        })

    def row_fields(self) -> dict[str,str]:
        task=self.task
        relation=task.get('relation_id') or task.get('relation') or ''
        defect=task.get('mutant_id') or task.get('defect_id') or task.get('mutant') or 'CLEAN'
        guarded=relation in {'MR04','MR09','MR10'} and defect in {'M01','M02','M03','M04','M05','M12'}
        mode='CLEAN' if defect=='CLEAN' else ('STAGE_ISOLATION' if guarded else 'FAULT_ACTIVE')
        return {
            'request_trace_json':json.dumps(_normal(task,self.work),sort_keys=True,separators=(',',':')),
            'action_trace_json':json.dumps(self.actions,sort_keys=True,separators=(',',':')),
            'command_trace_json':json.dumps(self.commands,sort_keys=True,separators=(',',':')),
            'artifact_identity_trace_json':json.dumps(self.artifacts,sort_keys=True,separators=(',',':')),
            'fault_activation_mode':mode,
            'fault_enabled_stage':str(task.get('fault_stage') or task.get('stage') or ('guarded-upstream' if guarded else 'declared-operator-stage')),
            'trace_completeness':'CURRENT_RUN_REQUEST_ACTION_COMMAND_ARTIFACT_AND_OBSERVATION',
        }


@contextmanager
def trace_session(task: dict[str,Any]) -> Iterator[TraceRecorder]:
    rec=TraceRecorder(task); token=_CURRENT.set(rec)
    try: yield rec
    finally: _CURRENT.reset(token)


def traced_run(*popenargs, **kwargs):
    rec=_CURRENT.get()
    args=kwargs.get('args',popenargs[0] if popenargs else [])
    paths=[]
    if isinstance(args,(list,tuple)):
        for value in args:
            try:
                p=Path(str(value))
                if p.exists() or str(value).endswith(('.c','.o','.so','.bin','.elf')): paths.append(p)
            except Exception: pass
    before={_normal(p,rec.work if rec else None):_sha(p) for p in paths} if rec else {}
    completed=_ORIGINAL_RUN(*popenargs,**kwargs)
    if rec:
        after={_normal(p,rec.work):_sha(p) for p in paths}
        rec.command(args,kwargs.get('cwd'),completed,before,after)
    return completed


def install_subprocess_proxy(module: Any) -> None:
    # A module-local proxy avoids changing subprocess.run for unrelated modules.
    current=getattr(module,'subprocess',None)
    if current is None or getattr(current,'_tosem02_proxy',False): return
    class Proxy:
        _tosem02_proxy=True
        def __getattr__(self,name):
            if name=='run': return traced_run
            return getattr(current,name)
    module.subprocess=Proxy()


def install_pipeline_method_tracing(cls: type) -> None:
    if getattr(cls,'_tosem02_trace_installed',False): return
    for name,fn in list(vars(cls).items()):
        if name.startswith('_') or not callable(fn): continue
        try: source=inspect.getsource(fn).lower()
        except Exception: source=''
        if not any(k in name.lower() or k in source for k in ('build','compile','embed','extract','transform','execute','run_host','relocat','remove','corrupt')): continue
        @functools.wraps(fn)
        def wrapper(self,*args,__fn=fn,__name=name,**kwargs):
            rec=_CURRENT.get()
            if rec: rec.action('begin',__name,{'args':args,'kwargs':kwargs})
            try:
                value=__fn(self,*args,**kwargs)
            except Exception as exc:
                if rec: rec.action('end',__name,error=f'{type(exc).__name__}: {exc}')
                raise
            if rec:
                rec.action('end',__name,result=value)
                def collect(v):
                    if isinstance(v,(str,os.PathLike,Path)):
                        p=Path(v)
                        if p.is_file(): rec.artifacts.append({'path':_normal(p,rec.work),'sha256':_sha(p),'bytes':p.stat().st_size})
                    elif dataclasses.is_dataclass(v): collect(dataclasses.asdict(v))
                    elif isinstance(v,dict):
                        for x in v.values(): collect(x)
                    elif isinstance(v,(list,tuple)):
                        for x in v: collect(x)
                    elif hasattr(v,'__dict__'): collect(vars(v))
                collect(value)
            return value
        setattr(cls,name,wrapper)
    cls._tosem02_trace_installed=True
