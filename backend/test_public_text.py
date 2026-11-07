import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.public_text import display_text, public_payload
from app.main import app
from app.llm import OpenAICompatLLM, AIError
from app.config import Settings

class PublicTextTests(unittest.TestCase):
    def test_internal_annotations_and_nested_parentheses_removed(self):
        self.assertEqual(display_text('你好（本次对话：用户问候（无需建任务））我在。'),'你好我在。')
        self.assertEqual(display_text('好呀(内部备注:不展示)。'),'好呀。')
        self.assertEqual(display_text('<think>内部推理\n不展示</think>你好。'),'你好。')
    def test_useful_parentheses_and_constraints_preserved(self):
        text='做数学题（第1至10题，不含附加题），写作文(不少于300字)。'
        self.assertEqual(display_text(text),text)
    def test_step_scope_unwrapped_without_losing_remaining_work(self):
        self.assertEqual(display_text('洗衣服（本次内容：放入衣物；加洗衣液）',step=True),'洗衣服\n放入衣物；加洗衣液')
        self.assertEqual(display_text('这一段还剩：加洗衣液',step=True),'这一段还剩：加洗衣液')
    def test_payload_ids_raw_inputs_and_state_are_not_modified(self):
        raw='保留（本次对话：用户原文）'
        payload={'reply':'你好（本次对话：问候）','step_id':raw,'original_input':raw,'command':{'text':raw},'completed_leaf_ids':['x'],'focus':{'step':{'current_step':'父（本次内容：子1；子2）'}},'events':[{'completed_actions':['动作（内部说明：隐藏）']}]}
        result=public_payload(payload)
        self.assertEqual(result['reply'],'你好');self.assertEqual(payload['reply'],'你好（本次对话：问候）')
        self.assertEqual(result['step_id'],raw);self.assertEqual(result['original_input'],raw);self.assertEqual(result['command'],payload['command'])
        self.assertEqual(result['completed_leaf_ids'],['x']);self.assertEqual(result['events'][0]['completed_actions'],['动作'])
    def test_real_ai_pure_internal_reply_is_a_retryable_error(self):
        ai=OpenAICompatLLM(Settings(llm_api_key='test'))
        with patch.object(ai,'_chat',return_value='（本次对话：仅内部信息）'),self.assertRaises(AIError):ai.reply('闲聊','你好')
        with patch.object(ai,'_chat',return_value='{"kind":"chat","reply":"（内部备注：不展示）","item_id":null}'),self.assertRaises(AIError):ai.route_message('你好',[])
    def test_http_filters_existing_cached_reply_without_changing_payload(self):
        data={'revision':2,'reply':'在呢（本次对话：打招呼）','focus':None,'items':[],'command':{'text':'原文（本次对话：保留）'}}
        with patch('app.main.memo.load',return_value={'days':{'today':{}},'active':None}),patch('app.main.memo.view',return_value=data),TestClient(app) as client:
            for _ in range(2):
                r=client.get('/api/session/state',params={'user_id':'u'})
                self.assertEqual(r.status_code,200);self.assertEqual(r.json()['reply'],'在呢');self.assertEqual(r.json()['command'],data['command'])
        self.assertEqual(data['reply'],'在呢（本次对话：打招呼）')
    def test_operation_replay_and_questions_are_filtered(self):
        data={'command':{'text':'原文（本次对话：保留）'},'result':{'reply':'好（内部说明：隐藏）','clarifications':[{'question':'几道题？（本次对话：待回答）'}]}}
        with patch('app.main.memo.operation',return_value=data),TestClient(app) as client:
            r=client.get('/api/today/operation',params={'user_id':'u','request_id':'key'}).json()
        self.assertEqual(r['command'],data['command']);self.assertEqual(r['result']['reply'],'好');self.assertEqual(r['result']['clarifications'][0]['question'],'几道题？')
