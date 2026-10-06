from __future__ import annotations
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from tosem02.evidence_boundary import (
    Candidate, ObservationUnavailable, ToolObservationError, first_valid_candidate,
    observe_elf_section, require_observed_output,
)

class EvidenceBoundaryTests(unittest.TestCase):
    def test_section_nonzero_is_tool_failure(self):
        calls=[]
        def run(argv, **kwargs):
            calls.append(argv)
            if '-S' in argv: return subprocess.CompletedProcess(argv,0,'  [ 1] .wm_record PROGBITS\n','')
            return subprocess.CompletedProcess(argv,2,'','objcopy failed')
        with self.assertRaises(ToolObservationError):
            observe_elf_section(__file__,'.wm_record',run=run)

    def test_section_success_without_dump_is_tool_failure(self):
        def run(argv, **kwargs):
            if '-S' in argv: return subprocess.CompletedProcess(argv,0,'  [ 1] .wm_record PROGBITS\n','')
            return subprocess.CompletedProcess(argv,0,'','')
        with self.assertRaises(ToolObservationError):
            observe_elf_section(__file__,'.wm_record',run=run)

    def test_true_missing_is_absent_without_dump(self):
        def run(argv, **kwargs):
            return subprocess.CompletedProcess(argv,0,'  [ 1] .text PROGBITS\n','')
        result=observe_elf_section(__file__,'.wm_record',run=run)
        self.assertEqual(result.status,'ABSENT')

    def test_section_checksum_bypass_is_not_reclassified_as_absence(self):
        # Presence and bytes are facts; checksum acceptance is a later predicate.
        def run(argv, **kwargs):
            if '-S' in argv: return subprocess.CompletedProcess(argv,0,'  [ 1] .wm_record PROGBITS\n','')
            target=Path(next(x.split('=',1)[1] for x in argv if x.startswith('.wm_record=')))
            target.write_bytes(b'WM\x01corrupt-checksum')
            return subprocess.CompletedProcess(argv,0,'','')
        result=observe_elf_section(__file__,'.wm_record',run=run)
        self.assertEqual(result.status,'PRESENT')
        self.assertEqual(result.data,b'WM\x01corrupt-checksum')

    def test_first_valid_parser_skips_fake_and_bad_candidates(self):
        magic=b'MAGC'
        def parse(blob):
            if len(blob)<6 or blob[:4]!=magic: return None
            n=blob[4]
            if blob[5]!=1 or len(blob)<6+n: return None
            return Candidate(0, 6+n, blob[6:6+n])
        absent=lambda:None
        data=magic+b'\xff\x00bad'+magic+b'\x02\x01OK'
        self.assertEqual(first_valid_candidate(data,magic,parse,absent).value,b'OK')

    def test_first_valid_parser_chooses_first_valid_of_multiple(self):
        magic=b'MAGC'
        def parse(blob):
            if len(blob)<6 or blob[:4]!=magic or blob[5]!=1:return None
            n=blob[4]
            return Candidate(0, 6+n, blob[6:6+n]) if len(blob)>=6+n else None
        data=magic+b'\x01\x01A'+magic+b'\x01\x01B'
        self.assertEqual(first_valid_candidate(data,magic,parse,lambda:None).value,b'A')

    def test_missing_output_is_inadmissible(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ObservationUnavailable):
                require_observed_output(returncode=0,path=Path(tmp)/'missing.txt')

    def test_nonzero_exit_is_inadmissible_even_if_outputs_match(self):
        with self.assertRaises(ObservationUnavailable):
            require_observed_output(returncode=1,path=None,stdout='same')


class RealToolSectionBoundaryTests(unittest.TestCase):
    def test_real_elf_missing_and_present_section_are_distinct(self):
        import shutil
        gcc=shutil.which('gcc'); objcopy=shutil.which('objcopy'); readelf=shutil.which('readelf')
        if not (gcc and objcopy and readelf): self.skipTest('ELF tools unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/'tiny.c'; binary=root/'tiny'; marked=root/'marked'; payload=root/'payload.bin'
            source.write_text('int main(void){return 0;}\n',encoding='utf-8')
            subprocess.run([gcc,str(source),'-o',str(binary)],check=True,capture_output=True)
            missing=observe_elf_section(binary,'.wm_record',objcopy=objcopy,readelf=readelf)
            self.assertEqual(missing.status,'ABSENT')
            payload.write_bytes(b'WM\x01corrupt-checksum')
            subprocess.run([objcopy,'--add-section',f'.wm_record={payload}',str(binary),str(marked)],check=True,capture_output=True)
            present=observe_elf_section(marked,'.wm_record',objcopy=objcopy,readelf=readelf)
            self.assertEqual(present.status,'PRESENT')
            self.assertEqual(present.data,payload.read_bytes())

if __name__=='__main__': unittest.main()
