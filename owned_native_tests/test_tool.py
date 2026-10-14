"""Owned wire-format, generated object and native execution regressions."""
import unittest
from owned_native_tool import tool
from tosem02.record import make_record


class NativeToolTests(unittest.TestCase):
    def test_independent_wire_implementation_matches_declared_format(self):
        for length in range(65):
            payload = bytes(range(length))
            self.assertEqual(tool.encode(payload,'key-alpha'), make_record(payload,'key-alpha'))
            self.assertEqual(tool.decode(tool.encode(payload,'key-alpha'),'key-alpha'),payload)

    def test_exact_record_boundary_and_typed_rejection(self):
        record = tool.encode(b'owned','key-alpha')
        for changed, key, kind in ((record,'key-beta','wrong-key'),
                                   (record[:-1],'key-alpha','malformed'),
                                   (record+b'\x00','key-alpha','malformed'),
                                   (record[:-1]+bytes([record[-1]^1]),'key-alpha','checksum')):
            with self.subTest(kind=kind), self.assertRaises(tool.Rejected) as error:
                tool.decode(changed,key)
            self.assertEqual(error.exception.kind,kind)

    def test_actual_objects_all_families_profiles_unsigned_boundaries(self):
        inputs = list(range(16)) + [2**32,2**63-1,2**63,tool.MASK]
        for family in tool.FAMILIES:
            for profile in tool.PROFILES:
                with self.subTest(family=family,profile=profile):
                    _, data = tool.compile_object(family,3,b'Morph-01','key-alpha',profile)
                    self.assertEqual(data[:7],b'\x7fELF\x02\x01\x01')
                    self.assertEqual(tool.extract(data,'key-alpha'),b'Morph-01')
                    self.assertEqual(tool.execute_owned(data,inputs),
                                     [tool.expected(family,3,x) for x in inputs])


if __name__ == '__main__':unittest.main()
