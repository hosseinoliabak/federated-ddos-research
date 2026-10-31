"""Small regression fixtures for scientific audit correctness."""

import tempfile, unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import audit_datasets as audit


class AuditChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.previous = audit.ROOT
        audit.ROOT = Path(self.tmp.name)

    def tearDown(self):
        audit.ROOT = self.previous
        self.tmp.cleanup()

    def inspect(self, text):
        p = audit.ROOT / "fixture.csv"
        p.write_text(text)
        return audit.inspect_file(p, "cicddos2019")

    def test_quality_and_iso_date(self):
        r, h, f = self.inspect(
            "src_ip,dst_ip,timestamp,label,flow_duration,value\na,b,2018-12-01 13:34:27.403713,DDoS,1,inf\na,b,2018-12-01 13:34:27.403713,DDoS,1,inf\nc,d,invalid,Normal,,oops\n"
        )
        self.assertEqual(r["rows"], 3)
        self.assertEqual(r["labels"], {"DDoS": 2, "Normal": 1})
        self.assertEqual(r["duplicate_record_hash_excess"], 1)
        self.assertEqual(r["missing_by_column"]["flow_duration"], 1)
        self.assertEqual(r["infinite_by_column"]["value"], 2)
        self.assertEqual(r["non_numeric_by_column"]["value"], 1)
        self.assertEqual(r["unparseable_timestamps"], 1)
        self.assertEqual(r["label_hour_counts"]["DDoS | 2018-12-01 13"], 2)

    def test_duplicates_cross_chunk_boundary(self):
        header = "timestamp,label,value\n"
        line = "2023-05-13 15:00:00,DDoS,1\n"
        r, h, f = self.inspect(header + line * 100001)
        self.assertEqual(r["rows"], 100001)
        self.assertEqual(r["duplicate_record_hash_excess"], 100000)
        self.assertEqual(r["label_hour_counts"]["DDoS | 2023-05-13 15"], 100001)


if __name__ == "__main__":
    unittest.main()
