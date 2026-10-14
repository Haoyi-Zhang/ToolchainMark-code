# Snapshot-coherent admission and an owned native object interface

The previous checksum-locality gate already excluded no-op, payload-changing
and structurally malformed follow-ups. This extension does not rediscover
those repairs. It binds strict rejection/locality to one captured view and
detects a net change between that view and tested extraction. The old v1/v2
rows remain under their original recorded facts; they are not v3 executions.

## Scoped MR10 invariant

Let S be captured source bytes, F the captured follow-up bytes, and W the
designated checksum slots in the accepted source carrier. The carrier
projection differs by representation: full artifact for strings, full .wmrec
section for sections, complete indexed carrier-name set for symbols. A source
capture must decode the requested payload. A follow-up capture must satisfy
the old payload/non-checksum equality, changed checksum, and strict checksum
rejection predicates. All decisions on each artifact are functions of one
captured byte buffer or one utility view of a private copy of that buffer.

For symbols, the strict decoder and locality decoder consume the same captured
name list, not two nm executions. For sections, the utilities observe the
private artifact copy. Shared record parsing and truthful utility behavior
remain assumptions; this is not an independent parser proof.

The executor also checks that the live follow-up equals F immediately before
and after tested extraction. If either comparison fails, the result is
INADMISSIBLE and cannot expose an extractor inconsistency. The hashes stored
in receipts identify the buffers; the admission comparisons use exact bytes,
so the operational invariant does not rely on collision resistance.

Proposition (detected net-change exclusion). If the final follow-up differs
from F after the tested extraction returns, that MR10 attempt cannot be
classified INCONSISTENT.

Proof. The post-extraction comparison records a false admission fact and exits
through InadmissibleCase before the relation predicate returns to evaluate.
Only a completed predicate branch can emit inconsistency. The same argument
applies to a detected change immediately before extraction.

Corollary (owned restoration control). Restoring the checksum to valid source
bytes before clean extraction makes extraction return the requested payload,
but changes F. It is therefore an invalid checksum-corruption experiment, not
a contradiction of the clean decoder. The preserved controlled red uses this
case and the old gate incorrectly attributed it.

Conditional preservation. If the observations faithfully describe the captured
bytes, the source/follow-up meet the carrier contract, and tested extraction
reads exactly the captured follow-up, the existing relative-soundness argument
applies without changing its rejection predicate. Additional gates only remove
attributions whose evidence is incomplete or changes; they do not establish
new watermark security or total correctness.

The final byte equality does NOT prove that no intermediate write occurred.
A restore-to-identical (ABA) sequence can evade endpoint equality. Concurrent
hostile writers, atomic filesystem snapshot guarantees, malicious utilities,
cryptographic authentication and universal race freedom are outside the claim.
Without faithful/immutable extraction input, the original soundness premise
remains unestablished. No such attack is constructed here.

## Separate native tool: semantic and record connection

owned_native_tool/tool.py imports no tosem02 encoder or decoder. It implements
the same published WMR2 experimental byte format independently and emits its
record as an LLVM-retained, readonly .wmrec data global. Its extractor reads
the actual little-endian ELF64 relocatable object, locates that section, and
checks an exact record boundary, version, length, key tag and payload checksum.
This is a separately coded owned fixture, not independent authorship/team,
a production watermark product, or an original/secure encoding.

Host input/result are unsigned 64-bit values. The four host families are affine
arithmetic, a quadratic, a rotate/xor, and a pure conditional. All arithmetic
is explicitly modulo 2^64; both rotate shifts are strictly less than 64. There
are no memory accesses or calls in host, no no-wrap flags, poison/undef, foreign
symbols, loops or nondeterministic input. The Python expected function uses
the same defined unsigned domain and masks the final mathematical result.

Lemma (host effect separation). Adding the isolated data record and llvm.used
retention declaration leaves the host instruction sequence and its parameters
unchanged. Under the specified LLVM instruction semantics, host therefore
computes the same unsigned function for every input with or without the record.

Proof. host does not reference owned_mark or any memory. Its expression uses
only its input, fixed constants, modular arithmetic, fixed shifts, unsigned
comparison and select. The extra global cannot change any operand, branch or
return value. No whole-compiler/MCJIT correctness conclusion follows from this
source-level argument; code generation, object loading and Windows ABI remain
trusted and receive finite native checks.

Record round trip is the experimental format's ordinary XOR-stream inversion
and checksum equality. The exact .wmrec boundary prevents an unrelated buffer
from substituting for its designated record in this owned object interface.
No robustness to arbitrary optimization/linking, stealth, attribution,
cryptographic authenticity, or post-link executable distribution is claimed.
LLVM's llvm.used declaration is a standard retention mechanism.

The native execution loads the actual emitted object using add_object_file,
not the source IR instead of that object. On this Windows runtime, llvmlite's
jitdefault code model appends -elf to its target-machine triple and emits ELF
objects with the native Windows calling convention. This does not execute a
Linux process, link a standalone executable, or validate GCC/Clang support.
The initial COFF-interface preflight failed and remains in private receipts;
the final interface was chosen from actual object bytes and primary API code.

## Comparison and interpretation

The native activity executes ten applicable relation shapes. MR06/MR07/MR11's
GCC/Clang requests and MR12 concurrent staging are not native capabilities
established by this new adapter. A native compile request names llvmlite and
its exact IR/backend profile; no GCC/Clang alias is fabricated. The original
executor defaults remain GCC/O2 for its original separate support envelope.

The direct comparator is ordinary source/follow-up byte-mask equality plus
checksum/payload observations and endpoint identity. It uses the same raw
information and the same typed extraction predicate. Equality with this
standard comparator is an executable consistency finding, not an advantage.
The locality-only variant is a derived observation ablation, not a fresh
execution of the old Linux implementation or Causal Testing Framework.

Native tests and replays establish finite owned executions, not novelty,
unseen-mechanism transfer, independent maintenance, full artifact acceptance,
cryptographic security or correctness of all relevant scientific assumptions.
