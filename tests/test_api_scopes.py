"""Tests for API scopes (RBAC minimal read-only)."""
import json, os, tempfile, threading, unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from digitalbrain.api.server import Handler
from digitalbrain.memory import SQLiteMemoryStore, MemoryType

class ApiScopeTests(unittest.TestCase):
    def test_scope_forbidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp)/'m.db'
            with SQLiteMemoryStore(db) as ms:
                ms.add_record(content='hi', memory_type=MemoryType.EPISODIC, source='test')
            old=os.environ.copy()
            try:
                os.environ['DIGITALBRAIN_API_TOKEN']='tok'
                os.environ['DIGITALBRAIN_API_SCOPES']='read:plans'
                os.environ['DIGITALBRAIN_MEMORY_DB']=str(db)
                Handler.config = type('C', (), {'token':'tok','scopes':{'read:plans'},'memory_db':str(db),'plan_db':None,'audit_db':None,'outcomes_db':None,'promotion_db':None})()
                srv=ThreadingHTTPServer(('127.0.0.1',0), Handler)
                t=threading.Thread(target=srv.handle_request); t.start()
                port=srv.server_port
                req=Request(f'http://127.0.0.1:{port}/v1/memory', headers={'Authorization':'Bearer tok'})
                with self.assertRaises(HTTPError) as ctx:
                    urlopen(req, timeout=2)
                self.assertEqual(ctx.exception.code, 403)
                t.join(timeout=2); srv.server_close()
            finally:
                os.environ.clear(); os.environ.update(old)

if __name__ == '__main__':
    unittest.main()
