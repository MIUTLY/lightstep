"""HTTP contracts used by the client's complete -> select chain and receipt outbox."""
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.db import DB
from test_memo import Fake

class FocusChainContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.db=DB(str(Path(self.tmp.name)/'test.db'))
        self.a=patch('app.services.db',self.db);self.b=patch('app.services.llm',Fake());self.a.start();self.b.start();self.client=TestClient(app)
    def tearDown(self):self.client.close();self.b.stop();self.a.stop();self.tmp.cleanup()
    def op(self,action,key=None,**kw):
        r=self.client.post('/api/today/command',json={'user_id':'u','request_id':key or uuid4().hex,'action':action,**kw})
        self.assertEqual(r.status_code,200,r.text);return r.json()
    def done(self,r):return self.op('complete',session_id=r['focus']['session_id'],step_id=r['focus']['step']['step_id'])
    def test_three_independent_tasks_start_at_first_step_and_finish_with_receipts(self):
        r=self.op('intake',text='写作业、看论文、洗衣服');ids=[i['id'] for i in r['items']]
        for n,ident in enumerate(ids):
            r=self.op('select',item_id=ident)
            self.assertEqual(r['focus']['step']['node_id'],'r0.0')
            self.assertEqual(r['focus']['presentation']['step_number'],1)
            for _ in range(10):r=self.done(r)
            self.assertIsNone(r['focus']);self.assertEqual(len(r['items']),2-n)
            self.assertEqual(len([e for e in r['events'] if e['kind']=='receipt']),n+1)
            self.assertFalse(r['navigation']['sidebar_locked'])
        self.assertTrue(r['all_completed'])
        self.assertEqual(r['events'][-2]['presentation']['step_number'],10)
    def test_end_freezes_unfinished_progress_and_duplicate_request_does_not_repeat_receipt(self):
        r=self.op('intake',text='三件事');ident=r['items'][0]['id'];r=self.op('select',item_id=ident)
        for _ in range(5):r=self.done(r)
        session=r['focus']['session_id'];r=self.op('end',key='end-one',session_id=session)
        again=self.op('end',key='end-one',session_id=session);self.assertEqual(r,again)
        self.assertIsNone(r['focus']);self.assertEqual(r['events'][0]['outcome'],'interrupted')
        self.assertEqual(len(r['items'][0]['progress']['remaining_leaf_ids']),5)
        self.assertEqual(r['events'][0]['presentation']['step_number'],6)
        resumed=self.op('select',item_id=ident);self.assertEqual(resumed['focus']['step']['node_id'],'r0.5')
    def test_next_generation_failure_keeps_previous_completion_and_next_item(self):
        r=self.op('intake',text='三件事');r=self.op('select',item_id=r['items'][0]['id'])
        for _ in range(10):r=self.done(r)
        next_id=r['suggested_item_id']
        from app.llm import AIError
        with patch('app.services.llm.decompose',side_effect=AIError('AI_TIMEOUT','超时')):
            failed=self.op('select',item_id=next_id)
        self.assertEqual(failed['operation']['status'],'failed');self.assertIsNone(failed['focus'])
        self.assertEqual(len(failed['items']),2);self.assertEqual(len(failed['events']),1)
        recovered=self.op('select',item_id=next_id);self.assertEqual(recovered['focus']['step']['node_id'],'r0.0')
