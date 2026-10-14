"""Owned pure ELF-object watermark fixture, without tosem02 imports.

Embed/compile/extract/execute are complete for this generated object interface.
This is a separate implementation of the declared WMR2 wire format, not an
independently maintained product or a new secure watermark scheme. Native
execution is restricted by the experiment to locally emitted benign objects.
No parser promise makes arbitrary machine code safe to execute.
"""
from __future__ import annotations
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import struct

VERSION = 'owned-elf-watermark-1'
MASK = (1 << 64) - 1
FAMILIES = ('affine', 'polynomial', 'rotate', 'conditional')
PROFILES = ('IR0-backend0', 'IR2-backend0')


class Rejected(ValueError):
    def __init__(self, kind):
        self.kind = kind
        super().__init__(kind)


def stream(data: bytes, key: str) -> bytes:
    sequence = b''.join(hashlib.sha256(key.encode('utf-8') +
                         i.to_bytes(4, 'big')).digest()
                        for i in range((len(data) + 31) // 32))
    return bytes(a ^ b for a, b in zip(data, sequence))


def encode(payload: bytes, key: str) -> bytes:
    if len(payload) > 65535:
        raise ValueError('payload outside retained 16-bit format')
    return (b'WMR2\x01' + hashlib.sha256(key.encode('utf-8')).digest()[:8] +
            len(payload).to_bytes(2, 'big') + stream(payload, key) +
            hashlib.sha256(payload).digest()[:8])


def decode(record: bytes, key: str, *, bypass=False) -> bytes:
    if record[:4] != b'WMR2':
        raise Rejected('absent')
    if len(record) < 23:
        raise Rejected('malformed')
    if record[4] != 1:
        raise Rejected('version')
    size = int.from_bytes(record[13:15], 'big')
    if len(record) != 23 + size:
        raise Rejected('malformed')
    if record[5:13] != hashlib.sha256(key.encode('utf-8')).digest()[:8]:
        raise Rejected('wrong-key')
    payload = stream(record[15:15 + size], key)
    if not bypass and record[-8:] != hashlib.sha256(payload).digest()[:8]:
        raise Rejected('checksum')
    return payload


def elf_sections(data: bytes) -> dict[str, tuple[int, int, int, int]]:
    """Owned little-endian ELF64 relocatable subset, not arbitrary ELF."""
    if len(data) < 64 or data[:7] != b'\x7fELF\x02\x01\x01':
        raise Rejected('malformed')
    header = struct.unpack_from('<16sHHIQQQIHHHHHH', data)
    _, kind, machine, version, _, _, table, _, size, _, _, stride, count, names_index = header
    if kind != 1 or machine != 62 or version != 1 or size != 64 or stride != 64 or not 2 <= count <= 256:
        raise Rejected('unsupported-object')
    if table < 64 or table + count * stride > len(data) or not 0 < names_index < count:
        raise Rejected('malformed')
    rows = [struct.unpack_from('<IIQQQQIIQQ', data, table + i * stride) for i in range(count)]
    names = rows[names_index]
    if names[1] != 3 or names[4] + names[5] > len(data):
        raise Rejected('malformed')
    name_data = data[names[4]:names[4] + names[5]]
    result = {}
    for row in rows[1:]:
        name_index, section_type, flags, _, offset, length, _, _, _, _ = row
        end = name_data.find(b'\0', name_index)
        if not 0 <= name_index < len(name_data) or end < 0:
            raise Rejected('malformed')
        name = name_data[name_index:end].decode('ascii')
        if name in result:
            raise Rejected('unsupported-object')
        if section_type != 8 and length and (offset < 64 or offset + length > len(data)):
            raise Rejected('malformed')
        result[name] = (offset, length, flags, section_type)
    return result


def record_bounds(data: bytes) -> tuple[int, int]:
    section = elf_sections(data).get('.wmrec')
    if section is None:
        raise Rejected('absent')
    start, size, flags, section_type = section
    # The fixture's authoritative carrier is readable nonexecuting data.
    if section_type != 1 or flags & 4 or not flags & 2:
        raise Rejected('unsupported-object')
    return start, start + size


def extract(data: bytes, key: str, *, bypass=False) -> bytes:
    start, end = record_bounds(data)
    return decode(data[start:end], key, bypass=bypass)


def expected(family: str, variant: int, value: int) -> int:
    if family not in FAMILIES or not 0 <= variant <= 15 or type(value) is not int or not 0 <= value <= MASK:
        raise ValueError('outside owned arithmetic interface')
    salt = variant + 11
    if family == 'affine':
        return ((value * 3 + 7) ^ salt) & MASK
    if family == 'polynomial':
        return (value * value + salt * value + 1) & MASK
    if family == 'rotate':
        return (((value << 7) | (value >> 57)) ^ salt) & MASK
    return (value * 5 if value > salt else value + salt) & MASK


def llvm_source(family: str, variant: int, payload: bytes | None, key: str,
                 triple: str) -> str:
    expected(family, variant, 0)
    salt = variant + 11
    bodies = {
        'affine': f'%a = mul i64 %x, 3\n%b = add i64 %a, 7\n%r = xor i64 %b, {salt}',
        'polynomial': f'%a = mul i64 %x, %x\n%b = mul i64 %x, {salt}\n%c = add i64 %a, %b\n%r = add i64 %c, 1',
        'rotate': f'%a = shl i64 %x, 7\n%b = lshr i64 %x, 57\n%c = or i64 %a, %b\n%r = xor i64 %c, {salt}',
        'conditional': f'%c = icmp ugt i64 %x, {salt}\n%a = mul i64 %x, 5\n%b = add i64 %x, {salt}\n%r = select i1 %c, i64 %a, i64 %b',
    }
    text = f'target triple = "{triple}"\ndefine i64 @host(i64 %x) {{\nentry:\n{bodies[family]}\nret i64 %r\n}}\n'
    if payload is not None:
        encoded = encode(payload, key)
        escaped = ''.join('\\' + f'{b:02X}' for b in encoded)
        text += (f'@owned_mark = constant [{len(encoded)} x i8] c"{escaped}", section ".wmrec", align 1\n'
                 '@llvm.used = appending global [1 x ptr] [ptr @owned_mark], section "llvm.metadata"\n')
    return text


def runtime():
    from llvmlite import binding as llvm
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()
    llvm.check_jit_execution()
    if llvm.get_default_triple() != 'x86_64-pc-windows-msvc':
        raise RuntimeError('This owned native experiment requires its declared Windows AMD64 ABI')
    return llvm


def compile_object(family: str, variant: int, payload: bytes | None, key: str,
                    profile: str) -> tuple[str, bytes]:
    if profile not in PROFILES:
        raise ValueError('unsupported build profile')
    llvm = runtime()
    source = llvm_source(family, variant, payload, key, llvm.get_default_triple())
    with llvm.parse_assembly(source) as module:
        module.verify()
        with llvm.Target.from_default_triple().create_target_machine(opt=0) as machine:
            if profile == 'IR2-backend0':
                with llvm.create_pipeline_tuning_options(speed_level=2) as tuning:
                    with llvm.create_pass_builder(machine, tuning) as builder:
                        with builder.getModulePassManager() as manager:
                            manager.run(module, builder)
            data = machine.emit_object(module)
    elf_sections(data)
    return source, data


def execute_owned(data: bytes, inputs: list[int]) -> list[int]:
    """Load the actual emitted object, not a substituted LLVM source module.

    The campaign calls this only on its owned emitted arithmetic objects and
    data-only carrier changes. This is not an arbitrary-object sandbox.
    """
    elf_sections(data)
    if any(type(x) is not int or not 0 <= x <= MASK for x in inputs):
        raise ValueError('invalid unsigned ABI input')
    llvm = runtime()
    machine = llvm.Target.from_default_triple().create_target_machine(opt=0)
    empty = llvm.parse_assembly('')
    with llvm.create_mcjit_compiler(empty, machine) as engine:
        object_file = llvm.ObjectFileRef.from_data(data)
        engine.add_object_file(object_file)
        engine.finalize_object()
        address = engine.get_function_address('host')
        if not address:
            raise RuntimeError('owned host symbol unavailable')
        function = ctypes.CFUNCTYPE(ctypes.c_uint64, ctypes.c_uint64)(address)
        return [int(function(value)) for value in inputs]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('embed')
    build.add_argument('--family', choices=FAMILIES, required=True)
    build.add_argument('--variant', type=int, required=True)
    build.add_argument('--payload-hex', required=True)
    build.add_argument('--key', required=True)
    build.add_argument('--profile', choices=PROFILES, required=True)
    build.add_argument('--out', type=Path, required=True)
    read = commands.add_parser('extract')
    read.add_argument('--artifact', type=Path, required=True)
    read.add_argument('--key', required=True)
    run = commands.add_parser('run-owned')
    run.add_argument('--directory', type=Path, required=True)
    run.add_argument('--inputs', type=int, nargs='+', required=True)
    args = parser.parse_args()
    if args.command == 'embed':
        args.out.mkdir(parents=True, exist_ok=False)
        source, data = compile_object(args.family, args.variant, bytes.fromhex(args.payload_hex), args.key, args.profile)
        (args.out / 'source.ll').write_text(source, encoding='utf-8')
        (args.out / 'artifact.obj').write_bytes(data)
        receipt = {'version':VERSION,'family':args.family,'variant':args.variant,'profile':args.profile,
                   'object_sha256':hashlib.sha256(data).hexdigest(),'object_bytes':len(data)}
        (args.out / 'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        print(json.dumps(receipt))
    elif args.command == 'extract':
        try:
            print(json.dumps({'kind':'payload','value':extract(args.artifact.read_bytes(), args.key).hex()}))
        except Rejected as error:
            print(json.dumps({'kind':'rejection','value':error.kind}))
    else:
        receipt = json.loads((args.directory / 'receipt.json').read_text())
        data = (args.directory / 'artifact.obj').read_bytes()
        if receipt['version'] != VERSION or hashlib.sha256(data).hexdigest() != receipt['object_sha256']:
            raise ValueError('object differs from local owned-generation receipt')
        values = execute_owned(data, args.inputs)
        reference = [expected(receipt['family'], receipt['variant'], x) for x in args.inputs]
        print(json.dumps({'inputs':args.inputs,'native':values,'expected':reference,'agree':values == reference}))
        if values != reference:
            raise SystemExit(1)


if __name__ == '__main__':
    main()
