"""Chat and scope clarification share the conversation; focus only starts when ready."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app
from app import memo
from app.db import DB
from app.llm import OpenAICompatLLM, Clarification, AIError
from app.config import Settings
from test_memo import Fake

class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.db=DB(str(Path(self.tmp.name)/'test.db'));self.ai=Fake()
        self.a=patch('app.services.db',self.db);self.b=patch('app.services.llm',self.ai)
        self.a.start();self.b.start();self.client=TestClient(app)
    def tearDown(self):
        self.client.close();self.b.stop();self.a.stop();self.tmp.cleanup()
    def chat(self,text,key=None):
        r=self.client.post('/api/chat',json={'user_id':'u','request_id':key or uuid4().hex,'message':text})
        self.assertEqual(r.status_code,200,r.text);return r.json()
    def op(self,action,**kw):return memo.execute(self.db,self.ai,'u',uuid4().hex,dict(action=action,**kw))
    def test_hello_uses_ai_reply_without_extraction_and_retries_once(self):
        with patch.object(self.ai,'route_message',return_value={'kind':'chat','reply':'在呢，想聊什么？','item_id':None}) as remote,patch.object(self.ai,'extract_tasks',side_effect=AssertionError('not a task')):
            r=self.chat('你好','hello');self.assertEqual(r['reply'],'在呢，想聊什么？');self.assertEqual(r['items'],[])
            self.assertEqual(self.chat('你好','hello'),r);self.assertEqual(remote.call_count,1)
    def test_chat_keeps_existing_tasks_and_events(self):
        before=self.op('intake',text='三项')
        with patch.object(self.ai,'route_message',return_value={'kind':'chat','reply':'我在。','item_id':None}):r=self.chat('今天有点累，想聊聊天')
        self.assertEqual(r['items'],before['items']);self.assertEqual(r['events'],before['events']);self.assertIsNone(r['focus'])
    def test_unclear_task_is_asked_in_chat_and_answered_before_focus(self):
        with patch.object(self.ai,'extract_tasks',return_value=['写作业']),patch.object(self.ai,'resolve_scope',side_effect=Clarification('什么作业，几道题？')):
            r=self.chat('写作业')
        self.assertEqual(r['operation']['status'],'needs_clarification');self.assertIsNone(r['focus']);self.assertFalse(r['can_enter_focus'])
        item=r['items'][0]['id']
        blocked=self.op('select',item_id=item);self.assertIsNone(blocked['focus'])
        with patch.object(self.ai,'route_message',return_value={'kind':'answer','reply':'好，十道数学题。','item_id':item}):r=self.chat('十道数学题')
        self.assertTrue(r['can_enter_focus']);self.assertEqual(r['clarifications'],[])
        with patch.object(self.ai,'resolve_scope',side_effect=AssertionError('already clarified')):r=self.op('select',item_id=item)
        self.assertIsNotNone(r['focus']);self.assertFalse(r['items'][0]['question'])
    def test_multiple_tasks_must_all_be_clear_before_select(self):
        with patch.object(self.ai,'resolve_scope',side_effect=Clarification('请说明具体范围')):
            r=self.chat('三个任务')
        ids=[i['id'] for i in r['items']]
        self.assertEqual(len(r['clarifications']),3)
        for item in ids:
            with patch.object(self.ai,'route_message',return_value={'kind':'answer','reply':'好的。','item_id':item}):r=self.chat('十道题')
            if item != ids[-1]:
                self.assertIsNone(self.op('select',item_id=item)['focus'])
        self.assertEqual(r['clarifications'],[])
        self.assertIsNotNone(self.op('select',item_id=ids[0])['focus'])

    def test_clear_goal_does_not_ask_and_focus_reuses_scope(self):
        r=self.chat('做十道数学题');self.assertEqual(r['clarifications'],[]);self.assertTrue(r['can_enter_focus'])
        with patch.object(self.ai,'resolve_scope',side_effect=AssertionError('already clarified')):self.op('select',item_id=r['items'][0]['id'])
    def test_ai_failure_preserves_input_and_existing_list(self):
        before=self.op('intake',text='三项')
        with patch.object(self.ai,'route_message',side_effect=AIError('AI_TIMEOUT','超时')):r=self.chat('你好','retry')
        self.assertEqual(r['operation']['status'],'failed');self.assertEqual(r['items'],before['items'])
        self.assertEqual(memo.operation(self.db,'u','retry')['command']['text'],'你好')
    def test_focus_disallows_general_chat(self):
        r=self.op('intake',text='三项');self.op('select',item_id=r['items'][0]['id'])
        response=self.client.post('/api/chat',json={'user_id':'u','request_id':'locked','message':'你好'})
        self.assertEqual(response.status_code,409)
    def test_real_adapter_distinguishes_chat_tasks_and_pending_answers(self):
        ai=OpenAICompatLLM(Settings(llm_api_key='test'))
        import json
        for result in ({'kind':'chat','reply':'你好呀。','item_id':None},{'kind':'tasks','reply':'记下啦。','item_id':None},{'kind':'answer','reply':'好的。','item_id':'one'}):
            with patch.object(ai,'_chat',return_value=json.dumps(result)):
                self.assertEqual(ai.route_message('输入',[{'id':'one','title':'作业','question':'几题？'}]),result)
        for raw in ('你好','{}','{"kind":"answer","reply":"好","item_id":"missing"}','{"kind":"answer","reply":"好","item_id":[]}'):
            with patch.object(ai,'_chat',return_value=raw),self.assertRaises(AIError):ai.route_message('输入',[])
