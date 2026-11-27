"""Tests for M7 API read-only baseline."""
import json, os, tempfile, threading, time, unittest
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from digitalbrain.api.server import Handler
from http.server import ThreadingHTTPServer
from digitalbrain.memory import SQLiteMemoryStore, MemoryType

class ApiTests(unittest.TestCase):
    def test_api_requires_token_and_serves_health(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp)/'m.db'
            with SQLiteMemoryStore(db) as ms:
                ms.add_record(type=MemoryType.NOTE, source='test', content='hi')
            old=os.environ.copy()
            try:
                os.environ['DIGITALBRAIN_API_TOKEN']='tok'
                os.environ['DIGITALBRAIN_MEMORY_DB']=str(db)
                Handler.config = type('C', (), {'token':'tok','memory_db':str(db),'plan_db':None,'audit_db':None,'outcomes_db':None})()
                srv=ThreadingHTTPServer(('127.0.0.1',0), Handler)
                t=threading.Thread(target=srv.handle_request); t.start()
                port=srv.server_port
                req=Request(f'http://127.0.0.1:{port}/v1/health')
                try:
                    urlopen(req, timeout=2)
                    self.fail('expected 401')
                except HTTPError as e:
                    self.assertEqual(e.code, 401)
                t.join(timeout=2); srv.server_close()

                srv=ThreadingHTTPServer(('127.0.0.1',0), Handler)
                t=threading.Thread(target=srv.handle_request); t.start()
                port=srv.server_port
                req=Request(f'http://127.0.0.1:{port}/v1/memory', headers={'Authorization':'Bearer tok'})
                resp=urlopen(req, timeout=2)
                data=json.loads(resp.read().decode('utf-8'))
                self.assertEqual(data['version'],'v1')
                self.assertGreaterEqual(len(data['memory']),1)
                t.join(timeout=2); srv.server_close()
            finally:
                os.environ.clear(); os.environ.update(old)

if __name__=='__main__':
    unittest.main()
