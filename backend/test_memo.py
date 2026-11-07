import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
_boot=tempfile.TemporaryDirectory()
os.environ['LIGHTSTEP_DB']=str(Path(_boot.name)/'boot.db')
from app import memo, task_forest
from app.db import DB
from app.llm import AIError, Clarification, OpenAICompatLLM
from app.config import Settings
from app.main import app
from fastapi.testclient import TestClient


def ten():
    return {'trees':[{'text':'完成十题','children':[{'text':f'做第{i}题','children':[{'text':f'完成第{i}题'}]} for i in range(1,11)]}]}

class Fake:
    def route_message(self,text,pending): return {'kind':'tasks','reply':'记下了。','item_id':None}
    calls=0
    def extract_tasks(self,text): return ['写作业','看论文','洗衣服']
    def resolve_scope(self,title,answers): return title+'：完成约定的十题'
    def decompose(self,scope): self.calls+=1; return ten()

class MemoTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.db=DB(str(Path(self.tmp.name)/'memo.db')); self.ai=Fake(); self.uid='u'
    def tearDown(self): self.tmp.cleanup()
    def op(self,action,key=None,**kw):
        return memo.execute(self.db,self.ai,self.uid,key or uuid4().hex,dict(action=action,**kw))
    def state(self): return memo.view(memo.load(self.db,self.uid))
    def start(self):
        r=self.op('intake',text='写作业，看论文，洗衣服')
        return self.op('select',item_id=r['items'][0]['id'])
    def finish_step(self,key=None):
        f=self.state()['focus'];return self.op('complete',key=key,session_id=f['session_id'],step_id=f['step']['step_id'])
    def test_removed_task_is_not_saved_as_a_completed_forest(self):
        r=self.start(); finished_id=r['focus']['item_id']
        for _ in range(10): self.finish_step()
        persisted=memo.load(DB(self.db.path),self.uid)
        day=persisted['days'][memo.today()]
        self.assertNotIn(finished_id,[i['id'] for i in day['items']])
        self.assertEqual(set(day['finished'][0]),{'id','title','scope'})
        self.assertEqual(day['finished'][0]['id'],finished_id)
        with self.assertRaises(Exception): self.op('select',item_id=finished_id)
        self.assertEqual(len(self.state()['items']),2)

    def test_reorder_after_removal_accepts_only_remaining_items(self):
        self.start()
        for _ in range(10): self.finish_step()
        r=self.state(); ids=[i['id'] for i in r['items']][::-1]
        r=self.op('reorder',date=r['date'],revision=r['revision'],item_ids=ids)
        self.assertEqual([i['id'] for i in r['items']],ids)
        self.assertEqual(len(memo.load(self.db,self.uid)['days'][r['date']]['finished']),1)

    def test_next_day_login_keeps_partial_progress_order_and_no_restarted_focus(self):
        with patch('app.memo.today',return_value='2026-11-07'):
            r=self.start()
            for _ in range(5): self.finish_step()
            self.op('end',session_id=r['focus']['session_id'])
            r=self.state(); ids=[i['id'] for i in r['items']][::-1]
            before=self.op('reorder',date=r['date'],revision=r['revision'],item_ids=ids)
        with patch('app.memo.today',return_value='2026-11-08'),patch('app.services.db',DB(self.db.path)),TestClient(app) as client:
            for _ in range(2):
                r=client.post('/api/session/open',json={'user_id':self.uid}).json()
                self.assertEqual(r['items'],before['items']); self.assertIsNone(r['focus'])
                self.assertEqual(r['date'],'2026-11-07'); self.assertEqual(r['today_date'],'2026-11-08')
                self.assertEqual(r['available_dates'],['2026-11-07'])
                self.assertEqual(r['events'],before['events'])
            with patch.object(self.ai,'decompose',side_effect=AssertionError('must reuse saved forest')):
                resumed=self.op('select',item_id=ids[-1])
            self.assertEqual(len(resumed['focus']['progress']['completed_leaf_ids']),5)

    def test_finished_yesterday_does_not_mark_empty_today_complete_or_reemit_events(self):
        with patch('app.memo.today',return_value='2026-11-07'),patch.object(self.ai,'extract_tasks',return_value=['十题']):
            self.start()
            for _ in range(10): self.finish_step()
            for e in self.state()['events']: self.op('ack',event_id=e['id'])
            before=memo.load(self.db,self.uid)
        with patch('app.memo.today',return_value='2026-11-08'):
            for _ in range(2):
                r=self.state(); self.assertEqual(r['items'],[])
                self.assertFalse(r['today_all_completed']); self.assertFalse(r['all_completed'])
                self.assertEqual(r['events'],[])
            historical=memo.view(memo.load(DB(self.db.path),self.uid),'2026-11-07')
            self.assertEqual(historical['items'],[]); self.assertTrue(historical['all_completed'])
        self.assertEqual(memo.load(self.db,self.uid),before)
        self.assertEqual(len(before['events']),2)

    def test_old_completed_rows_upgrade_without_dropping_pending_progress(self):
        r=self.start(); self.finish_step(); state=memo.load(self.db,self.uid)
        day=state['days'][r['date']]; old=day['items'][1]; old['completed']=True
        old_id=old['id']; expected=day['items'][0]['plan']
        with self.db._conn() as c:
            c.execute('UPDATE memo_state SET data=? WHERE user_id=?',(json.dumps(state),self.uid))
        restored=memo.load(DB(self.db.path),self.uid)
        self.assertNotIn(old_id,[i['id'] for i in restored['days'][r['date']]['items']])
        self.assertEqual(restored['days'][r['date']]['items'][0]['plan'],expected)
        self.assertEqual(restored['days'][r['date']]['finished'][0]['id'],old_id)
        self.assertEqual(restored['events'],state['events'])
        self.op('end',session_id=r['focus']['session_id'])
        with self.db._conn() as c:
            saved=json.loads(c.execute('SELECT data FROM memo_state WHERE user_id=?',(self.uid,)).fetchone()[0])
        self.assertNotIn(old_id,[i['id'] for i in saved['days'][r['date']]['items']])

    def test_new_day_intake_keeps_previous_pending_list_addressable(self):
        with patch('app.memo.today',return_value='2026-11-07'):
            before=self.op('intake',text='三件事')
        with patch('app.memo.today',return_value='2026-11-08'):
            self.op('intake',text='新三件事')
            r=self.state(); self.assertEqual(r['available_dates'],['2026-11-08','2026-11-07'])
            old=memo.view(memo.load(self.db,self.uid),'2026-11-07')
            self.assertEqual(old['items'],before['items'])
            self.assertFalse(r['all_completed'])

    def test_extract_order_and_default_prompt(self):
        r=self.op('intake',text='写作业，看论文，洗衣服')
        self.assertEqual([i['title'] for i in r['items']],['写作业','看论文','洗衣服']);self.assertIsNone(r['focus']);self.assertIn('写作业',r['reply'])
    def test_reorder_persisted_and_does_not_start_or_switch(self):
        r=self.start(); ids=[i['id'] for i in r['items']][::-1];f=r['focus']
        r=self.op('reorder',date=r['date'],revision=r['revision'],item_ids=ids)
        self.assertEqual(r['focus'],f)
        self.op('end',session_id=f['session_id'])
        restored=memo.view(memo.load(DB(self.db.path),self.uid));self.assertEqual([i['id'] for i in restored['items']],ids);self.assertIn('洗衣服',restored['reply'])
    def test_select_second_only(self):
        r=self.op('intake',text='三件事');r=self.op('select',item_id=r['items'][1]['id'])
        self.assertEqual(r['focus']['item_id'],r['items'][1]['id']);self.assertFalse(r['items'][0]['progress']['generated']);self.assertFalse(r['items'][2]['progress']['generated'])
    def test_five_of_ten_exit_and_resume(self):
        self.start()
        for _ in range(5):self.finish_step()
        f=self.state()['focus'];r=self.op('end',session_id=f['session_id'])
        self.assertIsNone(r['focus']);self.assertFalse(r['items'][0]['completed']);self.assertFalse(r['all_completed'])
        receipt=r['events'][0];self.assertEqual(receipt['outcome'],'interrupted');self.assertEqual(len(receipt['session_completed_leaf_ids']),5);self.assertEqual(len(receipt['remaining_leaf_ids']),5)
        with patch.object(self.ai,'decompose',side_effect=AssertionError('AI must not regenerate')):
            r=self.op('select',item_id=r['items'][0]['id'])
        self.assertIn('第6题',r['focus']['step']['current_step'])
    def test_only_finished_item_removed(self):
        self.start()
        for _ in range(10):r=self.finish_step()
        self.assertEqual([i['title'] for i in r['items']],['看论文','洗衣服']);self.assertIsNone(r['focus']);self.assertFalse(r['all_completed']);self.assertEqual(len(r['events']),1)
    def test_all_done_journal_once_and_idempotent_finish(self):
        r=self.op('intake',text='三件事')
        for item in r['items']:
            self.op('select',item_id=item['id'])
            for _ in range(9):self.finish_step()
            f=self.state()['focus'];cmd=dict(action='complete',session_id=f['session_id'],step_id=f['step']['step_id']);key=uuid4().hex
            first=memo.execute(self.db,self.ai,self.uid,key,cmd);again=memo.execute(self.db,self.ai,self.uid,key,cmd)
            self.assertEqual(first,again)
        r=self.state();self.assertTrue(r['all_completed']);self.assertEqual(len([e for e in r['events'] if e['kind']=='daily_journal']),1)
        for e in r['events']:self.op('ack',event_id=e['id'])
        self.assertEqual(self.state()['events'],[])
    def test_empty_day_not_complete(self):self.assertFalse(self.state()['all_completed'])
    def test_ai_fail_retry_and_original_input_preserved(self):
        before=self.state()
        with patch.object(self.ai,'extract_tasks',side_effect=AIError('AI_TIMEOUT','超时')):
            r=self.op('intake',key='req',text='我的原话')
        self.assertEqual(r['operation']['status'],'failed');self.assertEqual(self.state(),before)
        self.assertEqual(memo.operation(self.db,self.uid,'req')['command']['text'],'我的原话')
        r=self.op('intake',key='req',text='我的原话');self.assertEqual(len(r['items']),3)
        r=self.op('intake',key='req',text='我的原话');self.assertEqual(len(self.state()['items']),3)
    def test_select_failure_no_partial_forest(self):
        r=self.op('intake',text='三件事');before=self.state()
        with patch.object(self.ai,'decompose',side_effect=AIError('AI_TIMEOUT','超时')):
            r=self.op('select',item_id=r['items'][0]['id'])
        self.assertEqual(self.state(),before);self.assertEqual(r['operation']['status'],'failed')
    def test_clarification_before_focus(self):
        with patch.object(self.ai,'extract_tasks',return_value=['写作业']):r=self.op('intake',text='写作业')
        item=r['items'][0]['id']
        with patch.object(self.ai,'resolve_scope',side_effect=Clarification('哪份作业，多少题？')):
            r=self.op('select',item_id=item)
        self.assertIsNone(r['focus']);self.assertEqual(r['operation']['status'],'needs_clarification')
        r=self.op('select',item_id=item,answer='数学第1至10题');self.assertIsNotNone(r['focus'])
    def test_switches_do_not_call_ai_or_complete(self):
        self.start();before=self.state()['items'][0]['progress']
        for d in ['smaller','bigger','bigger','smaller']*3:
            f=self.state()['focus'];self.op('resize',session_id=f['session_id'],step_id=f['step']['step_id'],direction=d)
        self.assertEqual(self.state()['items'][0]['progress'],before);self.assertEqual(self.ai.calls,1)
    def test_stale_token_and_duplicate_end_no_second_event(self):
        self.start();f=self.state()['focus'];self.finish_step()
        with self.assertRaises(Exception):self.op('complete',session_id=f['session_id'],step_id=f['step']['step_id'])
        self.op('end',session_id=f['session_id'],key='end')
        self.op('end',session_id=f['session_id'],key='end')
        with self.assertRaises(Exception):self.op('end',session_id=f['session_id'])
        self.assertEqual(len(self.state()['events']),1)
    def test_parallel_progress_during_generation_preserved(self):
        self.start()
        def extraction(text):self.finish_step();return ['新任务']
        with patch.object(self.ai,'extract_tasks',side_effect=extraction),self.assertRaises(Exception):self.op('intake',text='新任务')
        self.assertEqual(len(self.state()['items']),3);self.assertEqual(len(self.state()['items'][0]['progress']['completed_leaf_ids']),1)
    def test_order_validation_and_one_focus(self):
        r=self.start();before=self.state()
        with self.assertRaises(Exception):self.op('select',item_id=r['items'][1]['id'])
        with self.assertRaises(Exception):self.op('reorder',date=r['date'],revision=r['revision'],item_ids=[r['items'][0]['id']]*3)
        self.assertEqual(self.state(),before)
    def test_new_day_keeps_old_progress_and_no_empty_journal(self):
        self.start();self.finish_step()
        with patch('app.memo.today',return_value='2099-01-01'):
            r=self.state();self.assertEqual(len(r['items']),3);self.assertIsNotNone(r['focus']);self.assertFalse(r['today_all_completed'])
    def test_http_default_chat_extracts_instead_of_combined_task(self):
        with patch('app.services.db',self.db),patch('app.services.llm',self.ai),TestClient(app) as client:
            r=client.post('/api/chat',json={'user_id':self.uid,'message':'三件事','request_id':'chat'})
            self.assertEqual(r.status_code,200,r.text);self.assertEqual(len(r.json()['items']),3)
            self.assertIsNone(self.db.get_active_task(self.uid))
            selected=client.post('/api/today/command',json={'user_id':self.uid,'request_id':'select','action':'select','item_id':r.json()['items'][1]['id']})
            self.assertEqual(selected.status_code,200,selected.text)
            self.assertIsNotNone(selected.json()['focus'])
            reopened=client.post('/api/session/open',json={'user_id':self.uid})
            self.assertEqual(reopened.json()['focus'],selected.json()['focus'])
            bad=client.post('/api/today/command',json={'user_id':self.uid,'request_id':'bad','action':'resize','direction':'bad'})
            self.assertEqual(bad.status_code,422)
    def test_append_after_daily_completion_updates_same_journal_identity(self):
        with patch.object(self.ai,'extract_tasks',return_value=['十题']):r=self.op('intake',text='十题')
        self.op('select',item_id=r['items'][0]['id'])
        for _ in range(10):self.finish_step()
        journal=next(e for e in self.state()['events'] if e['kind']=='daily_journal')
        with patch.object(self.ai,'extract_tasks',return_value=['再做十题']):r=self.op('intake',text='再做十题')
        self.assertFalse(r['all_completed'])
        updated=next(e for e in r['events'] if e['kind']=='daily_journal')
        self.assertFalse(updated['eligible']);self.assertEqual(updated['id'],journal['id'])
        self.op('select',item_id=r['items'][0]['id'])
        for _ in range(10):self.finish_step()
        updated=next(e for e in self.state()['events'] if e['kind']=='daily_journal')
        self.assertTrue(updated['eligible']);self.assertEqual(updated['id'],journal['id']);self.assertEqual(len(updated['tasks']),2)
    def test_cross_day_retry_uses_original_day(self):
        with patch('app.memo.today',return_value='2026-11-07'),patch.object(self.ai,'extract_tasks',side_effect=AIError('AI_TIMEOUT','超时')):
            self.op('intake',key='midnight',text='三件事')
        with patch('app.memo.today',return_value='2026-11-08'):
            self.op('intake',key='midnight',text='三件事')
            self.assertEqual(len(self.state()['items']),3)
        self.assertEqual(len(memo.view(memo.load(self.db,self.uid),'2026-11-07')['items']),3)
    def test_scope_adapter_rejects_invented_range(self):
        ai=OpenAICompatLLM(Settings(llm_api_key='test'))
        with patch.object(ai,'_chat',side_effect=['{"scope":"只打开作业"}','{"accepted":false}']),self.assertRaises(AIError):
            ai.resolve_scope('写十道作业题',[])
        with patch.object(ai,'_chat',return_value='{"clarification":"多少题？"}'),self.assertRaises(Clarification):
            ai.resolve_scope('写作业',[])
    def test_legacy_generation_cannot_overwrite_memo_focus(self):
        self.start()
        draft=self.db.begin_generation(self.uid,'旧任务','旧任务')
        self.assertFalse(self.db.install_generated_task(self.uid,draft,'旧任务',json.dumps(task_forest.new_plan(ten()))))
        self.assertIsNotNone(self.state()['focus'])

    def test_real_adapter_rejects_invalid_extraction_and_review(self):
        ai=OpenAICompatLLM(Settings(llm_api_key='test'))
        for responses in [['{}'],['{"tasks":[]}'],['{"tasks":[1]}'],['{"tasks":["洗衣服"]}','{"accepted":false}']]:
            with patch.object(ai,'_chat',side_effect=responses),self.assertRaises(AIError):ai.extract_tasks('洗衣服')
        with patch.object(ai,'_chat',side_effect=['{"tasks":["洗衣服"]}','{"accepted":true}']):self.assertEqual(ai.extract_tasks('洗衣服'),['洗衣服'])

if __name__=='__main__':unittest.main()
