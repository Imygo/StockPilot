import os
import unittest
from unittest.mock import patch
from database import config
from integrate_db import check_schema,REQUIRED,validate_rows
class ConfigTests(unittest.TestCase):
    def test_shared_stockpilot_database_allowed(self):
        with patch.dict(os.environ,{'STOCKPILOT_DB_NAME':'stockpilot_db','STOCKPILOT_DB_USER':'worker','STOCKPILOT_DB_PASSWORD':'test-only'},clear=True):
            self.assertEqual(config()['database'],'stockpilot_db')
    def test_explicit_portable_database(self):
        with patch.dict(os.environ,{'STOCKPILOT_DB_NAME':'team_stockpilot','STOCKPILOT_DB_USER':'worker','STOCKPILOT_DB_PASSWORD':'test-only','STOCKPILOT_DB_HOST':'db.example','STOCKPILOT_DB_PORT':'3307'},clear=True):
            self.assertEqual(config()['database'],'team_stockpilot');self.assertEqual(config()['port'],3307)
    def test_system_database_rejected(self):
        with patch.dict(os.environ,{'STOCKPILOT_DB_NAME':'mysql','STOCKPILOT_DB_USER':'root','STOCKPILOT_DB_PASSWORD':'test-only'},clear=True):
            with self.assertRaises(ValueError):config()
    def test_no_credentials_fails(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaises(ValueError):config()
class Cursor:
    def __init__(self,columns,keys):self.columns=columns;self.keys=keys;self.index=False
    def execute(self,sql):self.index=sql.startswith('SHOW INDEX')
    def fetchall(self):
        if not self.index:return [(c,) for c in self.columns]
        return [('table',0,name,i+1,col) for name,cols in self.keys.items() for i,col in enumerate(cols)]
class MigrationTests(unittest.TestCase):
    def test_existing_compatible_schema(self):
        check_schema(Cursor(REQUIRED,{'PRIMARY':('article_id','stock_code','model_version'),'other':('text_hash','stock_code','model_version')}))
    def test_missing_target_uniqueness_rejected(self):
        with self.assertRaises(ValueError):check_schema(Cursor(REQUIRED,{'PRIMARY':('article_id','model_version')}))
    def test_incompatible_table_rejected(self):
        with self.assertRaises(ValueError):check_schema(Cursor({'article_id'},{}))
    def test_invalid_import_rejected(self):
        with self.assertRaises(ValueError):validate_rows([{'stock_code':'bad'}])
