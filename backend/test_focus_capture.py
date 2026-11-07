import copy
import sqlite3
from contextlib import contextmanager
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
_boot=tempfile.TemporaryDirectory();os.environ['LIGHTSTEP_DB']=str(Path(_boot.name)/'boot.db')
from app import memo
from app.db import DB
from app.llm import AIError, Clarification, OpenAICompatLLM
from app.config import Settings
from app.main import app
from fastapi.testclient import TestClient


def proposal(kind='append',target=None):
    return {'tasks':['买菜','打电话'], 'placement':{'kind':kind,'target':target}}

class Fake:
    def extract_tasks(self,text):return ['写作业','洗衣服','看论文']
    def resolve_scope(self,title,answers):return '完成第1至10题'
    def decompose(self,scope):return {'trees':[{'text':'做十题','children':[{'text':f'做第{i}题','children':[{'text':f'完成第{i}题'}]} for i in range(1,11)]}]}
    def extract_focus_tasks(self,context):return proposal()

class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.db=DB(str(Path(self.tmp.name)/'test.db'));self.ai=Fake();self.uid='capture'
        r=self.op('intake',text='三件事');r=self.op('select',item_id=r['items'][0]['id']);self.sid=r['focus']['session_id']
        self.op('complete',session_id=self.sid,step_id=r['focus']['step']['step_id'])
        r=self.state();self.op('resize',session_id=self.sid,step_id=r['focus']['step']['step_id'],direction='smaller')
        self.before=copy.deepcopy(memo.load(self.db,self.uid))
    def tearDown(self):self.tmp.cleanup()
    def op(self,action,key=None,**data):return memo.execute(self.db,self.ai,self.uid,key or uuid4().hex,dict(action=action,**data))
    def state(self):return memo.view(memo.load(self.db,self.uid))
    def capture(self,key=None,**extra):return self.op('focus_capture',key=key,session_id=self.sid,text='买菜和打电话',**extra)
    def titles(self):return [i['title'] for i in self.state()['items']]
    def assert_preserved(self):
        now=memo.load(self.db,self.uid);self.assertEqual(now['active'],self.before['active']);self.assertEqual(now['events'],self.before['events'])
        old=self.before['days'][memo.today()]['items'];current=now['days'][memo.today()]['items']
        self.assertEqual([i for i in current if i['id'] in {x['id'] for x in old}],old)
    def test_append_multi_and_compact_success(self):
        r=self.capture();self.assertEqual(self.titles(),['写作业','洗衣服','看论文','买菜','打电话']);self.assertEqual(r['reply'],'收到，放到最后啦。')
        self.assertTrue(r['capture']['saved']);self.assertNotIn('items',r);self.assertNotIn('focus',r);self.assert_preserved()
    def test_insert_after_named_preserves_other_order_and_status(self):
        with patch.object(self.ai,'extract_focus_tasks',return_value=proposal('after_named','洗衣服')):r=self.capture()
        self.assertEqual(self.titles(),['写作业','洗衣服','买菜','打电话','看论文']);self.assertEqual(r['capture']['after_item_id'],self.before['days'][memo.today()]['items'][1]['id']);self.assert_preserved()
    def test_after_current_means_parent_task_not_step(self):
        with patch.object(self.ai,'extract_focus_tasks',return_value=proposal('after_current')):r=self.capture()
        self.assertEqual(self.titles(),['写作业','买菜','打电话','洗衣服','看论文']);self.assertEqual(r['capture']['after_item_id'],self.before['active']['item_id']);self.assert_preserved()
    def test_missing_target_asks_and_answer_keeps_original_batch(self):
        with patch.object(self.ai,'extract_focus_tasks',return_value=proposal('after_named','不存在')):r=self.capture(key='first')
        self.assertFalse(r['capture']['saved']);self.assertEqual(r['operation']['status'],'needs_clarification');self.assertEqual(len(self.titles()),3)
        with patch.object(self.ai,'extract_focus_tasks',return_value=proposal()) as ai:r=self.capture(key='answer',parent_request_id='first',answer='追加到最后')
        self.assertTrue(r['capture']['saved']);self.assertEqual(ai.call_args.args[0]['answers'][0]['answer'],'追加到最后')
        duplicate=self.capture(key='first');self.assertTrue(duplicate['capture']['saved']);self.assertEqual(len(self.titles()),5)
    def test_duplicate_names_require_explicit_choice_and_parallel_answers_deduplicate(self):
        with patch.object(self.ai,'extract_tasks',return_value=['洗衣服']):self.op('intake',text='再洗衣服')
        with patch.object(self.ai,'extract_focus_tasks',return_value=proposal('after_named','洗衣服')):r=self.capture(key='first')
        self.assertEqual(len(r['capture']['choices']),2);chosen=r['capture']['choices'][1]['id']
        with patch.object(self.ai,'extract_focus_tasks',side_effect=AssertionError('confirmed choice needs no AI')):
            r=self.capture(key='answer',parent_request_id='first',anchor_id=chosen)
            duplicate=self.capture(key='other-answer',parent_request_id='first',anchor_id=chosen)
        self.assertEqual(r['capture']['added_item_ids'],duplicate['capture']['added_item_ids']);self.assertEqual(len(self.titles()),6)
        self.capture(key='first')
        self.assertTrue(self.capture(key='answer',parent_request_id='first',anchor_id=chosen)['capture']['saved'])
        with self.assertRaises(Exception):
            self.op('focus_capture',key='other-answer',session_id=self.sid,text='另一批任务')
    def test_unknown_choice_rejected_without_addition(self):
        with patch.object(self.ai,'extract_focus_tasks',return_value=proposal('after_named','missing')):self.capture(key='first')
        with self.assertRaises(Exception):self.capture(parent_request_id='first',anchor_id='invented')
        self.assertEqual(len(self.titles()),3)
    def test_failure_preserves_input_and_retry_only_adds_once(self):
        with patch.object(self.ai,'extract_focus_tasks',side_effect=AIError('AI_TIMEOUT','超时')):r=self.capture(key='retry')
        self.assertEqual(r['operation']['status'],'failed');self.assertNotIn('收到',r['reply']);self.assertNotIn('items',r)
        self.assertEqual(memo.operation(self.db,self.uid,'retry')['command']['text'],'买菜和打电话');self.assert_preserved()
        r=self.capture(key='retry');self.assertEqual(self.capture(key='retry'),r);self.assertEqual(len(self.titles()),5)
    def test_control_words_never_exit_or_replace(self):
        r=self.op('focus_capture',session_id=self.sid,text='结束后写一份总结，把明天的安排换成洗衣服')
        self.assertTrue(r['capture']['saved']);self.assert_preserved()
    def test_stale_session_and_no_focus_do_not_call_ai(self):
        self.op('end',session_id=self.sid)
        with patch.object(self.ai,'extract_focus_tasks',side_effect=AssertionError('must not call')),self.assertRaises(Exception):self.capture()
        self.assertEqual(len(self.titles()),3)
    def test_progress_during_ai_is_not_overwritten(self):
        def during(ctx):
            f=self.state()['focus'];self.op('complete',session_id=self.sid,step_id=f['step']['step_id']);return proposal()
        with patch.object(self.ai,'extract_focus_tasks',side_effect=during),self.assertRaises(Exception):self.capture(key='race')
        self.assertEqual(len(self.titles()),3);self.assertEqual(len(self.state()['focus']['progress']['completed_leaf_ids']),2)
        self.capture(key='race');self.assertEqual(len(self.titles()),5)
    def test_end_during_ai_prevents_late_insert(self):
        def during(ctx):self.op('end',session_id=self.sid);return proposal()
        with patch.object(self.ai,'extract_focus_tasks',side_effect=during),self.assertRaises(Exception):self.capture()
        self.assertEqual(len(self.titles()),3);self.assertIsNone(self.state()['focus'])
    def test_reopen_and_retry_after_completed_capture(self):
        r=self.capture(key='saved');self.db=DB(self.db.path)
        with patch.object(self.ai,'extract_focus_tasks',side_effect=AssertionError('no regenerate')):again=self.capture(key='saved')
        self.assertEqual(r['capture'],again['capture']);self.assert_preserved()
    def test_http_parameters_and_no_full_memo_in_response(self):
        with patch('app.services.db',self.db),patch('app.services.llm',self.ai),TestClient(app) as c:
            data={'user_id':self.uid,'request_id':'http','session_id':self.sid,'text':'买菜和打电话'}
            r=c.post('/api/focus/capture',json=data);self.assertEqual(r.status_code,200,r.text);self.assertTrue(r.json()['capture']['saved']);self.assertNotIn('items',r.json())
            for extra in ({'action':'end'},{'private_note':'private'},{'answer':'a','anchor_id':'x'}):
                self.assertEqual(c.post('/api/focus/capture',json=dict(data,**extra)).status_code,422)
    def test_real_adapter_validates_model_position_and_semantics(self):
        ai=OpenAICompatLLM(Settings(llm_api_key='isolated'))
        bad=[{}, {'tasks':[],'placement':{'kind':'append','target':None}},proposal('priority'),proposal('after_current','洗衣服')]
        for value in bad:
            with patch.object(ai,'_chat',return_value=json.dumps(value)),self.assertRaises(AIError):ai.extract_focus_tasks({'original_input':'新任务'})
        with patch.object(ai,'_chat',side_effect=[json.dumps(proposal()),'{"accepted":false}']),self.assertRaises(AIError):ai.extract_focus_tasks({'original_input':'新任务'})
        with patch.object(ai,'_chat',side_effect=[json.dumps(proposal('after_current')),'{"accepted":true}']):self.assertEqual(ai.extract_focus_tasks({})['placement']['kind'],'after_current')
    def test_navigation_remains_locked_until_entire_task_done_or_explicit_end(self):
        self.assertTrue(self.state()['navigation']['sidebar_locked'])
        self.capture()
        f=self.state()['focus'];self.op('complete',session_id=self.sid,step_id=f['step']['step_id'])
        self.assertTrue(self.state()['navigation']['sidebar_locked'])
        self.op('end',session_id=self.sid)
        self.assertFalse(self.state()['navigation']['sidebar_locked'])
        self.assertFalse(self.state()['items'][0]['completed'])
    def test_whole_forest_completion_unlocks_navigation(self):
        while self.state()['focus']:
            f=self.state()['focus'];self.op('complete',session_id=self.sid,step_id=f['step']['step_id'])
        self.assertFalse(self.state()['navigation']['sidebar_locked'])
        self.assertTrue(self.state()['items'][0]['completed'])

    def test_database_commit_failure_rolls_back_and_retry_saves_once(self):
        original=self.db._conn
        count=0
        @contextmanager
        def fail_commit():
            nonlocal count
            count+=1
            with original() as c:
                yield c
                if count==2: raise sqlite3.OperationalError('isolated failure')
        data={'user_id':self.uid,'request_id':'disk-fail','session_id':self.sid,'text':'买菜和打电话'}
        with patch('app.services.db',self.db),patch('app.services.llm',self.ai),TestClient(app) as c:
            with patch.object(self.db,'_conn',fail_commit):r=c.post('/api/focus/capture',json=data)
            self.assertEqual(r.status_code,503);self.assertNotIn('收到',r.text);self.assertNotIn('isolated failure',r.text)
            self.assertEqual(len(self.titles()),3);self.assert_preserved()
            self.assertEqual(c.post('/api/focus/capture',json=data).status_code,200)
            self.assertEqual(c.post('/api/focus/capture',json=data).status_code,200)
            self.assertEqual(len(self.titles()),5)

    def test_ai_clarification_does_not_add(self):
        with patch.object(self.ai,'extract_focus_tasks',side_effect=Clarification('要新增什么任务？')):r=self.capture()
        self.assertEqual(r['operation']['status'],'needs_clarification');self.assertEqual(len(self.titles()),3);self.assert_preserved()

if __name__=='__main__':unittest.main()
