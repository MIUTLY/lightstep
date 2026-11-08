"""AI planning policy and manual progress contract. Isolated responses, not live model quality."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
from app import memo
from app.db import DB
from app.llm import OpenAICompatLLM, AIError
from app.config import Settings
from test_memo import Fake, ten

class ActionSupportTests(unittest.TestCase):
    def test_planning_and_review_both_receive_action_only_policy(self):
        ai=OpenAICompatLLM(Settings(llm_api_key='test'))
        review={'decision':'accept','relevant':True,'coverage':True,'parent_child_consistent':True,'no_duplicates':True}
        with patch.object(ai,'_chat',side_effect=[json.dumps(ten()),json.dumps(review)]) as calls:
            ai.decompose('做十道数学题')
        for call in calls.call_args_list:
            self.assertIn('只记录用户自报的行动进度',call.args[0])
            self.assertIn('用户明确目标',call.args[0])
        self.assertIn('relevant必须为false',calls.call_args_list[1].args[0])
    def test_scope_and_review_do_not_require_answer_evidence(self):
        ai=OpenAICompatLLM(Settings(llm_api_key='test'))
        with patch.object(ai,'_chat',side_effect=['{"scope":"做三道英语选择题"}','{"accepted":true}']) as calls:
            self.assertEqual(ai.resolve_scope('做三道英语选择题',[]),'做三道英语选择题')
        self.assertIn('不索要题目全文、答案或选项',calls.call_args_list[0].args[0])
        self.assertIn('未添加正确率、理由记录或成果验收',calls.call_args_list[1].args[0])
    def test_plan_review_can_reject_unnecessary_reporting_actions(self):
        ai=OpenAICompatLLM(Settings(llm_api_key='test'))
        bad={'trees':[{'text':'做题','children':[{'text':'作答并交理由','children':[{'text':'额外记录选项和理由'}]}]}]}
        review={'decision':'reject','relevant':False,'coverage':True,'parent_child_consistent':True,'no_duplicates':True}
        # 复核驳回后会重试（最多 3 轮「生成+复核」），给足 3 轮响应；最终仍然要如实报错
        with patch.object(ai,'_chat',side_effect=[json.dumps(bad),json.dumps(review)]*3) as calls,self.assertRaises(AIError) as error:
            ai.decompose('做一道选择题')
        self.assertEqual(error.exception.code,'AI_CONTENT_INVALID')
        self.assertEqual(calls.call_count,6)
    def test_plan_review_retry_can_recover(self):
        """第一轮复核驳回、第二轮通过：应该拿到计划而不是把用户挡在门外。"""
        ai=OpenAICompatLLM(Settings(llm_api_key='test'))
        bad={'trees':[{'text':'做题','children':[{'text':'作答并交理由','children':[{'text':'额外记录选项和理由'}]}]}]}
        reject={'decision':'reject','relevant':False,'coverage':True,'parent_child_consistent':True,'no_duplicates':True}
        accept={'decision':'accept','relevant':True,'coverage':True,'parent_child_consistent':True,'no_duplicates':True}
        with patch.object(ai,'_chat',side_effect=[json.dumps(bad),json.dumps(reject),json.dumps(ten()),json.dumps(accept)]) as calls:
            forest=ai.decompose('做十道数学题')
        self.assertIn('trees',forest)
        self.assertEqual(calls.call_count,4)
        # 第二轮提示里应该带上上一轮被判不合格的原因
        self.assertIn('复核判定不合格',calls.call_args_list[2].args[0])
    def test_manual_done_requires_no_answer_correctness_or_ai_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=DB(str(Path(tmp)/'test.db'));ai=Fake()
            def op(action,**kw):return memo.execute(db,ai,'u',uuid4().hex,dict(action=action,**kw))
            r=op('intake',text='三项');r=op('select',item_id=r['items'][0]['id'])
            with patch.object(ai,'decompose',side_effect=AssertionError('no grading')),patch.object(ai,'resolve_scope',side_effect=AssertionError('no grading')):
                for _ in range(10):
                    f=r['focus'];r=op('complete',session_id=f['session_id'],step_id=f['step']['step_id'])
            self.assertIsNone(r['focus']);self.assertEqual(len(r['items']),2)
            receipt=next(e for e in r['events'] if e['kind']=='receipt')
            self.assertEqual(receipt['outcome'],'completed');self.assertNotIn('correctness',receipt)
