"""Adapter for owned ELF objects; the tool's encoder/decoder are separate.

Only the string-record admission projection is reused. This does not execute
the original ELF executable/GCC/Clang/symbol/section support envelope.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import time

from tosem02.model import BuildResult, ExtractionError
from . import tool

HOST_INPUTS = (0,1,5,13,144,99991)


class OwnedPipeline:
    carrier = 'string'

    def __init__(self, profile, intervention='checksum', bypass=False):
        self.profile, self.intervention, self.bypass = profile, intervention, bypass
        self.builds, self.extractions, self.host_calls = [], [], []
        self.source_bytes = self.intervened_bytes = self.after_extract_bytes = None
        self.target = None

    def build(self, request):
        if request.compiler != 'llvmlite' or request.optimization != self.profile:
            raise ValueError('Requested native backend/profile was not supported')
        host = json.loads(request.host.read_text())
        started = time.perf_counter()
        source, data = tool.compile_object(host['family'], host['variant'],
                    request.payload if request.marked else None, request.key, self.profile)
        request.work_dir.mkdir(parents=True, exist_ok=False)
        ir = request.work_dir / 'source.ll'
        binary = request.work_dir / 'artifact.obj'
        ir.write_text(source, encoding='utf-8')
        binary.write_bytes(data)
        native = tool.execute_owned(binary.read_bytes(), list(HOST_INPUTS))
        reference = [tool.expected(host['family'],host['variant'],x) for x in HOST_INPUTS]
        if native != reference:
            raise RuntimeError('Owned object execution differs from its arithmetic specification')
        self.builds.append({'family':host['family'],'variant':host['variant'],
            'requested_compiler':request.compiler,'actual_compiler':'llvmlite',
            'requested_profile':request.optimization,'actual_profile':self.profile,
            'payload_hex':request.payload.hex(),'key':request.key,'marked':request.marked,
            'source':source,'object_hex':data.hex(),'object_sha256':hashlib.sha256(data).hexdigest(),
            'native_inputs':list(HOST_INPUTS),'native_outputs':native,'reference_outputs':reference,
            'compile_write_seconds':time.perf_counter()-started})
        return BuildResult(binary, ir, request.compiler, 'llvmlite', request.optimization,
                    self.profile, self.carrier, 'OWNED-CLEAN', ['llvmlite.emit_object', self.profile],
                    hashlib.sha256(source.encode()).hexdigest(), hashlib.sha256(data).hexdigest(),
                    0, '', request.payload.hex(), request.payload.hex(), request.key)

    def extract(self, binary, key):
        if self.target == binary and self.intervention == 'restore':
            binary.write_bytes(self.source_bytes)
        raw = binary.read_bytes()
        try:
            value = tool.extract(raw, key, bypass=self.bypass)
            observation = {'kind':'payload','value':value.hex()}
        except tool.Rejected as error:
            observation = {'kind':'rejection','value':error.kind}
            value = None
        self.extractions.append({'artifact_sha256':hashlib.sha256(raw).hexdigest(),
                                 'key':key,'observation':observation})
        if self.target == binary:
            self.after_extract_bytes = raw
        if value is None:
            raise ExtractionError(observation['value'], 'owned native decoder rejected')
        return value

    def remove_carrier(self, result, directory):
        directory.mkdir(parents=True, exist_ok=False)
        target = directory / 'removed.obj'
        data = bytearray(result.binary.read_bytes())
        start, _ = tool.record_bounds(data)
        data[start:start+4] = b'XXXX'
        target.write_bytes(data)
        return target

    def corrupt_carrier(self, result, directory):
        directory.mkdir(parents=True, exist_ok=False)
        target = directory / 'corrupt.obj'
        self.source_bytes = result.binary.read_bytes()
        data = bytearray(self.source_bytes)
        start, end = tool.record_bounds(data)
        if self.intervention in {'checksum','both','outside','restore'}:
            data[end-1] ^= 1
        if self.intervention in {'payload','both'}:
            data[start+15] ^= 1
        if self.intervention == 'outside':
            data[-1] ^= 1
        target.write_bytes(data)
        self.intervened_bytes, self.target = bytes(data), target
        return target

    def run_host(self, binary, value):
        data = binary.read_bytes()
        started = time.perf_counter()
        result = tool.execute_owned(data, [value])[0]
        self.host_calls.append({'artifact_sha256':hashlib.sha256(data).hexdigest(),
            'input':value,'native':result,'object_load_call_seconds':time.perf_counter()-started})
        return str(result)


def direct_integrity(pipeline, key):
    """Ordinary direct byte-mask/stability oracle on the same observations.

    Acquisition is shared, not timed as if free. No tosem02 parser is used.
    This standard checker is a full-contract comparator, not a novel method.
    """
    source, follow = pipeline.source_bytes, pipeline.intervened_bytes
    try:
        start, end = tool.record_bounds(source)
        source_payload = tool.extract(source, key)
        follow_payload = tool.extract(follow, key, bypass=True)
        try:
            tool.extract(follow, key)
            checksum_rejection = False
        except tool.Rejected as error:
            checksum_rejection = error.kind == 'checksum'
        valid = (len(source) == len(follow) and source[:end-8] == follow[:end-8]
                 and source[end:] == follow[end:] and source[end-8:end] != follow[end-8:end]
                 and source_payload == follow_payload and checksum_rejection)
        # A gate may stop before tested extraction. The intervention remains
        # available in that case; it does not create an invented extractor call.
        after = pipeline.after_extract_bytes
        valid = valid and (after is None or after == follow)
        if not valid:
            return 'INADMISSIBLE'
        observed = pipeline.extractions[-1]['observation']
        return 'SATISFIED' if observed == {'kind':'rejection','value':'checksum'} else 'INCONSISTENT'
    except tool.Rejected:
        return 'INADMISSIBLE'
