"""Real adapter + HTTP/storage regression, isolated transport only. No live AI claims."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

_boot = tempfile.TemporaryDirectory(prefix="lightstep-ai-boot-")
os.environ["LIGHTSTEP_DB"] = str(Path(_boot.name) / "boot.db")
os.environ["LLM_PROVIDER"] = "openai"

import httpx
from fastapi.testclient import TestClient
from app import services, task_forest
from app.config import Settings
from app.db import DB
from app.llm import OpenAICompatLLM, AIError, get_llm
from app.main import app

ACCEPT = {"decision": "accept", "relevant": True, "coverage": True,
          "parent_child_consistent": True, "no_duplicates": True}


def forest(goal="洗衣服"):
    # Per-goal transport fixtures, never selected by application code.
    steps = {
        "洗衣服": ["检查衣物洗涤标签并分开不能机洗的衣物", "把可机洗衣物放入洗衣机并加适量洗涤剂", "选择匹配标签的程序并启动", "洗涤结束后取出晾晒"],
        "洗碗": ["清除碗盘食物残渣", "用洗涤剂清洗碗盘", "冲净碗盘泡沫", "沥干并放好碗盘"],
        "整理桌面": ["把桌面纸张归类放好", "把桌面文具归位", "清走桌面垃圾", "擦干净腾出的桌面"],
    }[goal]
    return {"trees": [{"text": goal + "：准备和处理", "children": [
        {"text": steps[0] + "，然后" + steps[1], "children": [{"text": steps[0]}, {"text": steps[1]}]}]},
        {"text": goal + "：完成后续收尾", "children": [
            {"text": steps[2] + "，然后" + steps[3], "children": [{"text": steps[2]}, {"text": steps[3]}]}]}]}


class AIGenerationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="lightstep-ai-generation-")
        self.path = str(Path(self.tmp.name) / "test.db")
        self.db = DB(self.path)
        self.ai = OpenAICompatLLM(Settings(llm_api_key="isolated-not-real"))
        self.db_patch = patch("app.services.db", self.db); self.db_patch.start()
        self.ai_patch = patch("app.services.llm", self.ai); self.ai_patch.start()
        self.client = TestClient(app)
        self.uid = "ai-user"

    def tearDown(self):
        self.client.close(); self.ai_patch.stop(); self.db_patch.stop(); self.tmp.cleanup()

    def post(self, path, **data):
        r = self.client.post('/api/' + path, json={"user_id": self.uid, **data})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def generate(self, goal="洗衣服"):
        with patch.object(self.ai, '_chat', side_effect=[json.dumps(forest(goal)), json.dumps(ACCEPT)]) as remote:
            result = self.post('chat', message=goal)
        self.assertEqual(result['generation']['status'], 'succeeded')
        self.assertEqual(remote.call_count, 2)
        return result

    def begin(self):
        self.generate()
        self.post('task/choose_time', when='now'); self.post('task/commit', agree=True)
        self.post('step/resize', direction='smaller')
        self.post('step/complete', duration_ms=30000)

    def test_three_goals_use_exact_original_input_and_distinct_provider_content(self):
        for i, goal in enumerate(("洗衣服", "洗碗", "整理桌面")):
            self.uid = str(i)
            with patch.object(self.ai, '_chat', side_effect=[json.dumps(forest(goal)), json.dumps(ACCEPT)]) as remote:
                result = self.post('chat', message=goal)
            self.assertEqual(result['task']['title'], goal)
            self.assertEqual(json.loads(remote.call_args_list[0].args[1])['original_goal'], goal)
            plan = task_forest.read(self.db.get_active_task(self.uid))
            self.assertEqual([plan['nodes'][n]['text'] for n in task_forest.all_leaf_ids(plan)],
                [leaf['text'] for root in forest(goal)['trees'] for mid in root['children'] for leaf in mid['children']])
            if goal != '整理桌面':
                self.assertNotIn('桌面', result['task']['current_step'])

    def test_all_transport_errors_report_failure_without_task_or_success(self):
        cases = [(httpx.ConnectError("private"), 'AI_CONNECTION_FAILED'),
                 (httpx.ReadTimeout("private"), 'AI_TIMEOUT')]
        for error, code in cases:
            with self.subTest(code=code), patch('httpx.post', side_effect=error):
                result = self.post('chat', message='洗衣服')
                self.assertEqual(result['generation']['error']['code'], code)
                self.assertEqual(result['state'], 'idle'); self.assertIsNone(result['task'])
                self.assertNotIn('准备好', result['reply']); self.assertNotIn('private', result['reply'])
                self.assertIsNone(self.db.get_active_task(self.uid))

    def test_unconfigured_and_mock_provider_cannot_generate(self):
        for settings in (Settings(), Settings(llm_provider='mock', llm_api_key='irrelevant')):
            with patch('app.services.llm', OpenAICompatLLM(settings)), patch('httpx.post') as remote:
                result = self.post('chat', message='洗碗')
            self.assertEqual(result['generation']['error']['code'], 'AI_NOT_CONFIGURED')
            remote.assert_not_called(); self.assertIsNone(self.db.get_active_task(self.uid))
        with patch('app.llm.settings', Settings(llm_provider='mock')):
            self.assertIsInstance(get_llm(), OpenAICompatLLM)

    def test_structurally_valid_wrong_goal_is_rejected_by_review(self):
        reject = dict(ACCEPT, decision='reject', relevant=False, coverage=False)
        with patch.object(self.ai, '_chat', side_effect=[json.dumps(forest('整理桌面')), json.dumps(reject)]) as remote:
            result = self.post('chat', message='洗衣服')
        self.assertEqual(result['generation']['error']['code'], 'AI_CONTENT_INVALID')
        review_data = json.loads(remote.call_args_list[1].args[1])
        self.assertEqual(review_data['original_goal'], '洗衣服')
        self.assertEqual(review_data['forest'], forest('整理桌面'))
        self.assertIsNone(self.db.get_active_task(self.uid))

    def test_invalid_json_structure_and_invalid_review_never_create_task(self):
        responses = [['no JSON'], ['[]'], ['{"fine":["桌面"]}'],
                     [json.dumps(forest()), '{}'], [json.dumps(forest()), json.dumps(dict(ACCEPT, coverage='yes'))]]
        for sequence in responses:
            with self.subTest(sequence=sequence), patch.object(self.ai, '_chat', side_effect=sequence):
                result = self.post('chat', message='洗衣服')
            self.assertEqual(result['generation']['error']['code'], 'AI_INVALID_RESPONSE')
            self.assertIsNone(self.db.get_active_task(self.uid))

    def test_each_semantic_check_must_pass(self):
        for field in ('relevant', 'coverage', 'parent_child_consistent', 'no_duplicates'):
            with patch.object(self.ai, '_chat', side_effect=[json.dumps(forest()), json.dumps(dict(ACCEPT, **{field: False}))]):
                result = self.post('chat', message='洗衣服')
            self.assertEqual(result['generation']['error']['code'], 'AI_CONTENT_INVALID')
            self.assertIsNone(self.db.get_active_task(self.uid))

    def test_failed_replacement_preserves_full_task_progress_and_draft_retry_after_reopen(self):
        self.begin()
        before = self.db.get_active_task(self.uid)
        with patch('httpx.post', side_effect=httpx.ReadTimeout('private')):
            result = self.post('chat', message='换成洗碗')
        self.assertEqual(self.db.get_active_task(self.uid), before)
        self.assertEqual(result['task']['steps_done'], 1)
        self.assertEqual(result['generation']['original_input'], '换成洗碗')
        self.assertEqual(result['generation']['goal'], '洗碗')
        # A new DB instance represents a server restart; status read does not expose task snapshot.
        with patch('app.services.db', DB(self.path)):
            draft = self.client.get('/api/task/generation', params={'user_id': self.uid}).json()['generation']
            self.assertEqual(draft['status'], 'failed'); self.assertNotIn('expected_task', draft)
            reopened = self.post('session/open')
            self.assertEqual(reopened['task'], result['task'])
            with patch.object(self.ai, '_chat', side_effect=[json.dumps(forest('洗碗')), json.dumps(ACCEPT)]):
                retried = self.post('task/generation/retry', generation_id=draft['generation_id'])
        self.assertEqual(retried['generation']['status'], 'succeeded')
        self.assertEqual(retried['task']['title'], '洗碗')
        self.assertEqual(retried['task']['steps_done'], 0)
        self.assertNotEqual(retried['generation']['generation_id'], draft['generation_id'])

    def test_generation_failure_does_not_roll_over_yesterdays_task(self):
        self.begin()
        with self.db._conn() as c:
            c.execute("UPDATE users SET last_seen='2000-01-01' WHERE user_id=?", (self.uid,))
        before = self.db.get_active_task(self.uid)
        with patch('httpx.post', side_effect=httpx.ConnectError('private')):
            self.post('chat', message='换成洗碗')
        self.assertEqual(self.db.get_active_task(self.uid), before)

    def test_failed_replacement_keeps_scheduled_start_notes_and_day_log(self):
        self.generate()
        self.post('task/choose_time', when='in_5_minutes')
        self.post('note', content='记下此事')
        def tables():
            with self.db._conn() as c:
                return {name: [tuple(r) for r in c.execute('SELECT * FROM ' + name)] for name in
                        ('active_task', 'task_start_reminders', 'notes', 'day_log', 'handoff', 'users')}
        before = tables()
        with patch.object(self.ai, '_chat', return_value='{}'):
            self.post('chat', message='换成洗碗')
        self.assertEqual(tables(), before)

    def test_unavailable_ai_does_not_affect_saved_switch_complete_and_reload(self):
        self.begin()
        completed = task_forest.read(self.db.get_active_task(self.uid))['completed_leaf_ids']
        with patch('app.services.llm', OpenAICompatLLM(Settings())), patch('httpx.post') as remote:
            for direction in ('bigger', 'smaller', 'bigger', 'bigger', 'smaller', 'smaller'):
                self.post('step/resize', direction=direction)
                self.assertEqual(task_forest.read(self.db.get_active_task(self.uid))['completed_leaf_ids'], completed)
            self.post('session/open')
            self.client.get('/api/session/state', params={'user_id': self.uid})
            self.post('step/complete', duration_ms=30000)
        remote.assert_not_called()
        self.assertGreater(self.db.get_active_task(self.uid)['steps_done'], 1)

    def test_clarification_preserves_task_then_answer_uses_original_goal(self):
        self.begin(); before = self.db.get_active_task(self.uid)
        with patch.object(self.ai, '_chat', return_value=json.dumps({'clarification': '这次用洗衣机还是手洗？'})):
            result = self.post('chat', message='换成洗衣服')
        self.assertEqual(self.db.get_active_task(self.uid), before)
        self.assertEqual(result['generation']['status'], 'needs_clarification')
        self.assertNotIn('准备好', result['reply'])
        with patch.object(self.ai, '_chat', side_effect=[json.dumps(forest()), json.dumps(ACCEPT)]) as remote:
            result = self.post('task/generation/answer', generation_id=result['generation']['generation_id'], answer='用洗衣机')
        self.assertEqual(result['generation']['status'], 'succeeded')
        payload = json.loads(json.loads(remote.call_args_list[0].args[1])['original_goal'])
        self.assertEqual(payload['original_goal'], '洗衣服')
        self.assertEqual(payload['clarification_answers'][0]['answer'], '用洗衣机')

    def test_old_generation_cannot_overwrite_progress_made_while_waiting(self):
        self.begin()
        def during_generation(*args, **kwargs):
            self.post('step/complete', duration_ms=30000)
            return json.dumps(forest('洗碗'))
        count = 0
        def chat(*args, **kwargs):
            nonlocal count
            count += 1
            return during_generation() if count == 1 else json.dumps(ACCEPT)
        with patch.object(self.ai, '_chat', side_effect=chat):
            result = self.post('chat', message='换成洗碗')
        self.assertEqual(result['generation']['error']['code'], 'TASK_CHANGED')
        self.assertEqual(self.db.get_active_task(self.uid)['title'], '洗衣服')
        self.assertEqual(self.db.get_active_task(self.uid)['steps_done'], 2)

    def test_superseded_generation_cannot_commit_or_overwrite_newer_draft(self):
        old = self.db.begin_generation(self.uid, '洗衣服', '洗衣服')
        latest = self.db.begin_generation(self.uid, '洗碗', '洗碗')
        plan = json.dumps(task_forest.new_plan(forest()))
        self.assertFalse(self.db.install_generated_task(self.uid, old, '洗衣服', plan))
        self.assertFalse(self.db.finish_generation(self.uid, old['generation_id'], status='failed'))
        self.assertEqual(self.db.get_generation(self.uid), latest)
        self.assertIsNone(self.db.get_active_task(self.uid))

    def test_stale_retry_and_success_retry_rejected(self):
        result = self.generate()
        for gid in (result['generation']['generation_id'], 'stale'):
            r = self.client.post('/api/task/generation/retry', json={'user_id': self.uid, 'generation_id': gid})
            self.assertEqual(r.status_code, 409)

    def test_end_to_end_budget_prevents_late_commit(self):
        with patch.object(self.ai, '_chat', return_value=json.dumps(forest())), \
             patch('app.llm.monotonic', side_effect=[0, 1, 31]):
            result = self.post('chat', message='洗衣服')
        self.assertEqual(result['generation']['error']['code'], 'AI_TIMEOUT')
        self.assertIsNone(self.db.get_active_task(self.uid))

    def test_raw_goal_is_not_over_stripped_and_explicit_generate_supports_any_goal(self):
        raw = '今天只把两件羊毛衫手洗，不洗其他衣服'
        with patch.object(self.ai, '_chat', side_effect=[json.dumps(forest()), json.dumps(ACCEPT)]) as remote:
            result = self.post('task/generate', goal=raw)
        self.assertEqual(json.loads(remote.call_args_list[0].args[1])['original_goal'], raw)
        self.assertEqual(result['generation']['original_input'], raw)

    def test_chat_clarification_answer_and_commands_remain_separate(self):
        self.begin()
        with patch.object(self.ai, '_chat', return_value=json.dumps({'clarification': '这次用洗衣机还是手洗？'})):
            self.post('chat', message='换成洗衣服')
        before = self.db.get_active_task(self.uid)
        self.post('chat', message='轻一点')
        self.assertEqual(self.db.get_generation(self.uid)['status'], 'needs_clarification')
        self.assertEqual(self.db.get_active_task(self.uid)['steps_done'], before['steps_done'])
        with patch.object(self.ai, '_chat', side_effect=[json.dumps(forest()), json.dumps(ACCEPT)]) as remote:
            result = self.post('chat', message='补充：用洗衣机')
        self.assertEqual(result['generation']['status'], 'succeeded')
        self.assertIn('用洗衣机', remote.call_args_list[0].args[1])

    def test_authorization_rate_limit_and_service_errors_are_safe_and_retryable(self):
        for status, code in ((401, 'AI_AUTH_FAILED'), (403, 'AI_AUTH_FAILED'),
                             (429, 'AI_RATE_LIMITED'), (500, 'AI_SERVICE_FAILED')):
            response = httpx.Response(status, request=httpx.Request('POST', 'https://provider.invalid'),
                                      text='private-provider-content')
            with patch('httpx.post', return_value=response):
                result = self.post('chat', message='洗衣服')
            self.assertEqual(result['generation']['error']['code'], code)
            self.assertTrue(result['generation']['error']['retryable'])
            self.assertNotIn('private-provider-content', result['reply'])
            self.assertIsNone(self.db.get_active_task(self.uid))

    def test_review_timeout_preserves_existing_task_without_installing_unreviewed_forest(self):
        self.begin(); before = self.db.get_active_task(self.uid)
        with patch.object(self.ai, '_chat', side_effect=[json.dumps(forest('洗碗')),
                AIError('AI_TIMEOUT', 'AI响应超时，请重试。', 504)]):
            result = self.post('chat', message='换成洗碗')
        self.assertEqual(result['generation']['error']['code'], 'AI_TIMEOUT')
        self.assertEqual(self.db.get_active_task(self.uid), before)

    def test_malformed_provider_envelopes_are_explicit_failures(self):
        for data in ({}, {'choices': []}, {'choices': [{'message': {'content': ''}}]},
                     {'choices': [{'message': {'content': '{'}, 'finish_reason': 'length'}]}):
            response = httpx.Response(200, request=httpx.Request('POST', 'https://provider.invalid'), json=data)
            with patch('httpx.post', return_value=response):
                result = self.post('chat', message='洗碗')
            self.assertEqual(result['generation']['error']['code'], 'AI_INVALID_RESPONSE')
            self.assertIsNone(self.db.get_active_task(self.uid))

    def test_chat_retry_is_available_without_frontend_new_route(self):
        with patch.object(self.ai, '_chat', return_value='{}'):
            self.post('chat', message='洗碗')
        with patch.object(self.ai, '_chat', side_effect=[json.dumps(forest('洗碗')), json.dumps(ACCEPT)]):
            result = self.post('chat', message='重试生成')
        self.assertEqual(result['generation']['status'], 'succeeded')


if __name__ == '__main__':
    unittest.main()
