import csv
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock
from import_ticks import REQUIRED, load_minutes, save_minutes

class TickImportTests(unittest.TestCase):
    def test_sort_deduplicate_and_aggregate(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "ticks_test.csv"
            rows = [
                ["005930","20261019","090059","110","120","10","10","2"],
                ["005930","20261019","090001","100","100","0","0","3"],
                ["005930","20261019","090030","90","110","10","10","5"],
                ["005930","20261019","090030","90","110","10","10","5"],
                ["005930","20261019","090100","95","130","5","5","5"],
            ]
            with path.open("w",encoding="utf-8-sig",newline="") as f:
                writer=csv.writer(f); writer.writerow(REQUIRED); writer.writerows(rows)
            result,total,unique=load_minutes([path])
            self.assertEqual((total,unique,len(result)),(5,4,2))
            self.assertEqual(result[0][0],"005930")
            self.assertEqual(result[0][2:],(110,120,10,10,100,110,90))
            self.assertEqual(result[1][4:6],(-5,-5))
            rows[0][1]="20260230"
            with path.open("w",encoding="utf-8",newline="") as f:
                writer=csv.writer(f); writer.writerow(REQUIRED); writer.writerows(rows)
            with self.assertRaisesRegex(ValueError,":2"):
                load_minutes([path])

    def test_commit_and_rollback(self):
        db=MagicMock()
        save_minutes(db,[(1,)*9])
        db.commit.assert_called_once()
        db.rollback.assert_not_called()
        db.reset_mock()
        db.cursor.return_value.__enter__.return_value.executemany.side_effect=RuntimeError("test")
        with self.assertRaises(RuntimeError):
            save_minutes(db,[(1,)*9])
        db.rollback.assert_called_once()
        db.commit.assert_not_called()

if __name__=="__main__":
    unittest.main()
