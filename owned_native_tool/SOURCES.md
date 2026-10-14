# Source bindings and closest-standard overlap

- Clark et al., Testing Causality in Scientific Modelling Software, TOSEM 2024,
  DOI 10.1145/3607184. Complete author accepted PDF inspected: 44 physical pages
  (one repository cover plus 43 manuscript pages), including references and
  spline appendix; not conflated with the published 42-page record.
  https://eprints.whiterose.ac.uk/id/eprint/200672/1/2022_CITCOM_CTFJournal_accepted.pdf
  Definitions 3.1/3.4/3.5/3.7 already separate scenario, intervention, expected
  causal effect and oracle. Sections 4.3-4.4 allow experimental/observational
  collection, scenario filtering and custom oracles. The abstract framework can
  host artifact-local checks supplied by a domain adapter. The paper does not
  specify this WMR2 snapshot/byte-mask realization; that is an implementation
  distinction, not proof of universal novelty or stronger theory.
- Foster et al., The Causal Testing Framework, JOSS 2025, complete three-page
  primary article inspected, DOI 10.21105/joss.07739:
  https://joss.theoj.org/papers/10.21105/joss.07739.pdf
  Its causal graph/test/data separation, estimands, adequacy, missing-variable
  and feedback extensions are not new contributions of this fixture. No CTF
  runtime or common-DAG effect-estimation baseline was executed here.
- Versioned llvmlite execution API:
  https://llvmlite.readthedocs.io/en/v0.46.0/user-guide/binding/execution-engine.html
  https://raw.githubusercontent.com/numba/llvmlite/v0.46.0/ffi/executionengine.cpp
  The add_object_file contract and wrapper transfer actual object ownership to
  the engine; this fixture does not substitute source IR for object execution.
  Installed executionengine.py/object_file.py were read completely; relevant
  targets.py constructor/emit implementation was inspected. Installed
  llvmlite 0.46.0 targets.py appends -elf on Windows jitdefault code model.
  LLVM/compiler/MCJIT/ABI are trusted; no full compiler-source verification.
- ELF primary format, claim-critical header/section structure and flags:
  https://refspecs.linuxfoundation.org/elf/gabi4+/ch4.eheader.html
  https://refspecs.linuxfoundation.org/elf/gabi4+/ch4.sheader.html
  Only a generated little-endian ELF64 relocatable subset is accepted; no
  general ELF parser, loader or security guarantee is inferred.
- LLVM instruction/retention semantics:
  https://llvm.org/docs/LangRef.html
  Flagless modular arithmetic, fixed-width shifts, unsigned comparison/select,
  and llvm.used are standard mechanisms. This is not full manual coverage.

The ordinary same-information byte-mask plus endpoint-identity comparator
implements the same bounded integrity contract and ties the new gate. Plain
checksums, retention globals, immutable observation buffers, and direct contract
oracles are not claimed as original mechanisms. Primary inspection supplies
scope/overlap evidence, not scientific acceptance. The other bibliography
entries have not all received new full-text inspection in this extension.

Official current TOSEM author guidelines returned 403 at
https://dl.acm.org/journal/tosem/author-guidelines . Compilation, primary reading
and finite native counts do not close venue eligibility, submission-format,
disclosure, scientific-acceptance or novelty gates. Existing licenses and author
metadata are unchanged; private source PDFs/runtime are not redistributed.
