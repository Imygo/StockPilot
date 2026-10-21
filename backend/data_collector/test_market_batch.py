import asyncio
import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, patch
import market_batch as batch
import data_collector as core

class BatchTests(unittest.TestCase):
    def stock(self, code, market):
        return dict(stock_code=code, stock_name="테스트", market=market, market_cap=100, previous_volume=1000, rank=1)

    def test_master_ranks_both_formats_and_excludes_etf(self):
        for market, (_, width, offset, vol_offset) in batch.MASTER.items():
            content=[]
            for code, cap, group in [("005930",100,"ST"),("000660",200,"ST"),("111111",999,"EF")]:
                tail=list(" " * width); tail[:2]=group
                tail[offset:offset+9]=f"{999-cap:09d}"
                tail[vol_offset:vol_offset+12]=f"{cap:012d}"
                content.append(code.ljust(9)+"KR0000000000"+"테스트"+"".join(tail))
            ranked=batch.parse_master(("\n".join(content)+"\n").encode("cp949"),market)
            self.assertEqual([r["stock_code"] for r in ranked],["000660","005930"])

    def test_universe_validation(self):
        stocks=[self.stock("005930","KOSPI"),self.stock("000001","KOSDAQ")]
        self.assertEqual(len(batch.validate_universe({"stocks":stocks,"basis":"KIS master previous trading day volume"},1)),2)
        with self.assertRaises(ValueError):
            batch.validate_universe({"stocks":stocks,"basis":"KIS master previous trading day volume"},20)

    def test_router_preserves_47_fields_and_separates_symbols(self):
        with TemporaryDirectory() as directory, patch.object(batch,"DATA",Path(directory)):
            stocks=[self.stock("005930","KOSPI"),self.stock("000660","KOSDAQ")]
            recorder=batch.SymbolRecorder(core,stocks,"test")
            columns=["MKSC_SHRN_ISCD"] + [f"F{i}" for i in range(1,45)] + ["VI_STND_PRC"]
            rows=[["005930"]+["0"]*45+["2"],["000660"]+["1"]*45+["3"]]
            raw="0|H0STCNT0|002|"+"^".join(v for row in rows for v in row)
            try:
                self.assertEqual(recorder.write(raw,columns),2)
                for code, extra in [("005930","2"),("000660","3")]:
                    with recorder.recorders[code].path.open(encoding="utf-8-sig") as f:
                        records=list(csv.DictReader(f))
                    self.assertEqual(len(records),1)
                    self.assertEqual(records[0]["MKSC_SHRN_ISCD"],code)
                    self.assertEqual(records[0]["EXTRA_FIELD_47"],extra)
                    self.assertEqual(len(records[0]),47)
            finally:
                recorder.close()

    def test_import_manifest_atomic_and_dry_run(self):
        stocks=[self.stock("005930","KOSPI")]
        with TemporaryDirectory() as directory:
            p=Path(directory)/"run.json"; p.write_text('{"kind":"tick"}',encoding="utf-8")
            connection=MagicMock(); fake_core=MagicMock()
            fake_core.connect_db.return_value=connection
            with patch.object(batch,"manifest_rows",return_value=(stocks,[(1,)*9])):
                batch.import_manifest(fake_core,p,True)
                fake_core.connect_db.assert_not_called()
                batch.import_manifest(fake_core,p)
                connection.commit.assert_called_once()
                connection.reset_mock()
                connection.cursor.return_value.__enter__.return_value.executemany.side_effect=RuntimeError("db failure")
                with self.assertRaises(RuntimeError):
                    batch.import_manifest(fake_core,p)
                connection.rollback.assert_called_once()
                connection.commit.assert_not_called()

if __name__=="__main__":
    unittest.main()
