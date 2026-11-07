"""父子关系、剩余叶子进度、持久化、并发与模型边界；全离线。"""
import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

_boot = tempfile.TemporaryDirectory(prefix="lightstep-forest-boot-")
os.environ["LLM_PROVIDER"] = "openai"
os.environ["LIGHTSTEP_DB"] = str(Path(_boot.name) / "boot.db")

from fastapi.testclient import TestClient
from app import services, task_forest
from app.config import Settings
from app.db import DB
from tests.fakes import decompose_forest
from tests.fakes import MockLLM
from app.llm import OpenAICompatLLM, AIError
from app.main import app


def example():
    def medium(number, leaves):
        return {"text": f"中任务{number}", "children": [{"text": f"轻任务{i}"} for i in leaves]}
    return {"trees": [
        {"text": "重任务1", "children": [medium(1, (1, 2)), medium(2, (3, 4))]},
        {"text": "重任务2", "children": [medium(3, (5,)), medium(4, (6, 7, 8))]},
        {"text": "重任务3", "children": [medium(5, (9, 10))]},
    ]}


class ForestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="lightstep-forest-")
        self.db = DB(str(Path(self.temp.name) / "test.db"))
        self.llm = MockLLM()
        self.swap_db = patch("app.services.db", self.db)
        self.swap_llm = patch("app.services.llm", self.llm)
        self.swap_plan = patch.object(self.llm, "decompose", return_value=example())
        self.swap_db.start(); self.swap_llm.start(); self.planning = self.swap_plan.start()
        self.client = TestClient(app)
        self.uid = "forest-user"

    def tearDown(self):
        self.client.close(); self.swap_plan.stop(); self.swap_llm.stop(); self.swap_db.stop(); self.temp.cleanup()

    def post(self, path, **data):
        r = self.client.post('/api/' + path, json={"user_id": self.uid, **data})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def begin(self):
        result = self.post('chat', message='我要写论文')
        self.post('task/choose_time', when='now'); self.post('task/commit', agree=True)
        return result

    def resize(self, direction):
        return self.post('step/resize', direction=direction)['task']

    def complete(self, duration_ms=30000, **data):
        return self.post('step/complete', duration_ms=duration_ms, **data)

    def task(self):
        return self.client.get('/api/session/state', params={"user_id": self.uid}).json()['task']

    def plan(self):
        return task_forest.read(self.db.get_active_task(self.uid))

    def done_texts(self):
        plan = self.plan()
        return [plan['nodes'][leaf]['text'] for leaf in plan['completed_leaf_ids']]

    def test_default_is_first_medium_despite_friction_and_emotion(self):
        self.db.get_friction(self.uid, 'writing')
        with self.db._conn() as c:
            c.execute('UPDATE friction SET default_level=1 WHERE user_id=?', (self.uid,))
        with patch.object(self.llm, 'detect_emotion', return_value='焦虑'):
            result = self.begin()
        self.assertTrue(result['task']['current_step'].startswith('中任务1（本次内容：'))
        self.assertEqual(result['task']['granularity'], 'normal')
        self.assertEqual(result['task']['plan_format'], 'forest_v1')
        self.assertTrue(self.task()['current_step'].startswith('中任务1（本次内容：'))
        self.assertEqual(self.planning.call_count, 1)

    def test_medium_to_heavy_then_medium_then_light_keeps_all_content(self):
        self.begin()
        self.assertTrue(self.resize('bigger')['current_step'].startswith('重任务1（本次内容：'))
        self.assertTrue(self.resize('smaller')['current_step'].startswith('中任务1（本次内容：'))
        self.assertEqual(self.resize('smaller')['current_step'], '轻任务1')
        self.assertEqual(self.done_texts(), [])
        self.assertEqual(len(task_forest.all_leaf_ids(self.plan())), 10)
        self.assertEqual(self.planning.call_count, 1)

    def test_medium1_done_medium2_to_heavy_exposes_only_remaining(self):
        self.begin(); self.complete()
        self.assertTrue(self.task()['current_step'].startswith('中任务2（本次内容：'))
        result = self.resize('bigger')
        self.assertEqual(result['parent_id'], None)
        self.assertEqual(result['current_step'], '这一段还剩：轻任务3；轻任务4')
        self.assertNotIn('轻任务1', result['current_step'])
        self.assertEqual(self.done_texts(), ['轻任务1', '轻任务2'])
        self.assertEqual(len(result['remaining_leaf_ids']), 2)
        self.assertTrue(self.resize('smaller')['current_step'].startswith('中任务2（本次内容：'))

    def test_medium2_to_light_starts_at_light3(self):
        self.begin(); self.complete()
        self.assertEqual(self.resize('smaller')['current_step'], '轻任务3')
        self.assertEqual(self.done_texts(), ['轻任务1', '轻任务2'])

    def test_light1_done_return_to_medium_only_requests_light2(self):
        self.begin(); self.resize('smaller'); self.complete()
        self.assertEqual(self.task()['current_step'], '轻任务2')
        result = self.resize('bigger')
        self.assertEqual(result['current_step'], '这一段还剩：轻任务2')
        self.assertEqual(len(result['remaining_leaf_ids']), 1)
        self.assertEqual(self.done_texts(), ['轻任务1'])

    def test_repeated_switches_and_boundaries_do_not_change_completion_records(self):
        self.begin(); self.resize('smaller'); self.complete()
        before = (self.plan()['completed_leaf_ids'], self.db.get_today_summary(self.uid), self.task()['steps_done'])
        for direction in ['smaller', 'bigger', 'bigger', 'bigger', 'smaller', 'smaller'] * 4:
            result = self.resize(direction)
            self.assertEqual((self.plan()['completed_leaf_ids'], self.db.get_today_summary(self.uid), result['steps_done']), before)
        self.assertEqual(self.planning.call_count, 1)

    def test_completed_parent_children_never_reappear_and_next_tree_is_selected(self):
        self.begin(); self.resize('bigger')
        result = self.complete()
        self.assertTrue(result['task']['current_step'].startswith('重任务2（本次内容：'))
        self.assertEqual(result['task']['granularity'], 'coarse')
        self.assertEqual(self.done_texts(), ['轻任务1', '轻任务2', '轻任务3', '轻任务4'])
        self.assertTrue(self.resize('smaller')['current_step'].startswith('中任务3（本次内容：'))
        self.assertEqual(self.resize('smaller')['current_step'], '轻任务5')

    def test_parent_completion_consumes_only_its_remaining_leaves(self):
        self.begin(); self.resize('smaller'); self.complete()
        self.resize('bigger')
        result = self.complete()
        self.assertTrue(result['task']['current_step'].startswith('中任务2（本次内容：'))
        self.assertEqual(self.done_texts(), ['轻任务1', '轻任务2'])
        self.assertEqual(result['task']['steps_done'], 2)

    def test_reopen_and_database_restart_preserve_tree_done_and_step_id(self):
        self.begin(); self.resize('smaller'); self.complete(); self.resize('bigger')
        before = self.task(); plan = self.plan()
        with patch('app.services.db', DB(self.db.path)):
            opened = self.post('session/open')['task']
            self.assertEqual(opened, before)
            self.assertEqual(self.plan(), plan)
        self.assertEqual(self.planning.call_count, 1)

    def test_roundtrip_switch_back_and_read_have_stable_scope_identity(self):
        self.begin(); before = self.task()
        self.resize('bigger'); self.resize('smaller')
        self.assertEqual(self.task()['step_id'], before['step_id'])
        self.resize('smaller'); self.complete(); self.resize('bigger')
        self.assertEqual(self.task()['node_id'], before['node_id'])
        self.assertNotEqual(self.task()['step_id'], before['step_id'])

    def test_parent_display_explicitly_includes_exact_work_consumed_by_completion(self):
        self.begin(); self.resize('bigger')
        before = self.task(); plan = self.plan()
        texts = [plan['nodes'][leaf]['text'] for leaf in before['remaining_leaf_ids']]
        for text in texts:
            self.assertIn(text, before['current_step'])
        self.complete()
        self.assertEqual(self.done_texts(), texts)

    def test_timing_does_not_override_selected_level_or_default_medium(self):
        self.begin(); self.complete(1)
        self.assertEqual(self.task()['granularity'], 'normal')
        self.resize('smaller'); self.complete(1)
        self.assertEqual(self.task()['granularity'], 'fine')
        self.resize('bigger'); self.complete(180000)
        self.assertEqual(self.task()['granularity'], 'normal')

    def test_buttons_and_chat_labels_dispatch_both_directions(self):
        self.begin()
        result = self.post('chat', message='轻一点')
        self.assertEqual(result['task']['current_step'], '轻任务1')
        self.assertEqual(result['buttons'], ['轻一点', '完成这一步', '重一点', '今天到这吧'])
        result = self.post('chat', message='重一点')
        self.assertTrue(result['task']['current_step'].startswith('中任务1（本次内容：'))
        result = self.post('chat', message='轻一点是什么意思？')
        self.assertTrue(result['task']['current_step'].startswith('中任务1（本次内容：'))

    def test_resize_before_start_preserves_state_and_appointment(self):
        self.post('chat', message='写论文')
        due = self.post('task/choose_time', when='in_5_minutes')['task']['start_due_at']
        result = self.resize('smaller')
        self.assertEqual(result['state'], 'ready')
        self.assertEqual(result['start_due_at'], due)
        self.post('task/choose_time', when='now')
        self.assertEqual(self.resize('bigger')['state'], 'committing')

    def test_handoff_roundtrip_keeps_forest_progress_and_current_scope(self):
        self.begin(); self.resize('smaller'); self.complete(); self.resize('bigger')
        before = self.task()
        with self.db._conn() as c:
            c.execute('UPDATE users SET last_seen=? WHERE user_id=?', ((datetime.now().date() - timedelta(days=1)).isoformat(), self.uid))
        offered = self.post('session/open')
        self.assertIn('接着', offered['reply'])
        resumed = self.post('handoff/resume')['task']
        self.assertEqual(resumed, before)
        self.assertEqual(self.done_texts(), ['轻任务1'])

    def test_end_message_names_only_generated_session_scope(self):
        self.begin(); self.resize('bigger')
        for _ in range(3):
            result = self.complete()
        self.assertEqual(result['state'], 'done')
        self.assertIn('这次拆出的步骤', result['reply'])
        self.assertNotIn('写论文', result['reply'])
        self.assertIsNone(self.db.get_active_task(self.uid))

    def test_stale_step_token_rejected_with_no_progress_or_friction_write(self):
        self.begin(); old = self.task()['step_id']; self.resize('smaller')
        with self.db._conn() as c:
            before = {name: [tuple(r) for r in c.execute(f'SELECT * FROM {name}')] for name in ['active_task', 'day_log', 'friction']}
        for path, payload in [('step/complete', {'duration_ms': 1}), ('step/resize', {'direction': 'bigger'})]:
            response = self.client.post('/api/' + path, json={'user_id': self.uid, 'step_id': old, **payload})
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()['detail']['code'], 'STALE_TASK_STEP')
        with self.db._conn() as c:
            after = {name: [tuple(r) for r in c.execute(f'SELECT * FROM {name}')] for name in before}
        self.assertEqual(before, after)

    def test_old_resize_snapshot_cannot_overwrite_newer_completed_leaves(self):
        self.begin(); snapshot = self.db.get_active_task(self.uid)
        old_plan = task_forest.read(snapshot); task_forest.resize(old_plan, 'bigger')
        self.complete(); before = self.db.get_active_task(self.uid)
        applied = self.db.update_plan_if_current(snapshot, json.dumps({task_forest.KEY: old_plan}), 3, 0)
        self.assertFalse(applied)
        self.assertEqual(self.db.get_active_task(self.uid), before)
        self.assertEqual(self.done_texts(), ['轻任务1', '轻任务2'])

    def test_parallel_same_token_completions_consume_exactly_one_displayed_batch(self):
        self.begin(); token = self.task()['step_id']
        with ThreadPoolExecutor(max_workers=3) as pool:
            responses = list(pool.map(lambda _: self.client.post('/api/step/complete', json={
                'user_id': self.uid, 'duration_ms': 30000, 'step_id': token}), range(3)))
        self.assertEqual(sorted(r.status_code for r in responses), [200, 409, 409])
        self.assertEqual(self.done_texts(), ['轻任务1', '轻任务2'])
        self.assertEqual(self.task()['steps_done'], 1)
        self.assertEqual(self.db.get_today_summary(self.uid)['steps_done'], 1)

    def test_unknown_or_corrupt_stored_forest_is_not_guessed_or_deleted(self):
        self.begin()
        task = self.db.get_active_task(self.uid); levels = json.loads(task['levels_json'])
        levels[task_forest.KEY]['version'] = 99
        self.db.update_active_task(self.uid, levels_json=json.dumps(levels))
        before = self.db.get_active_task(self.uid)
        r = self.client.get('/api/session/state', params={'user_id': self.uid})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()['detail']['code'], 'INVALID_TASK_PLAN')
        self.assertEqual(self.db.get_active_task(self.uid), before)

    def test_legacy_three_lists_and_queue_are_not_converted_or_lost(self):
        for queued in (False, True):
            levels = {'fine': ['细A', '细B'], 'normal': ['旧A', '旧B', '旧C'], 'coarse': ['粗A', '粗B']}
            if queued:
                from app.step_plan import new_plan
                levels = new_plan(levels, 2)
            self.db.create_active_task(self.uid, '旧任务', json.dumps(levels), 2, current_idx=1, steps_done=1, state='executing')
            before = self.db.get_active_task(self.uid)
            self.assertEqual(self.task()['current_step'], '旧B')
            self.assertEqual(self.task()['plan_format'], 'legacy')
            self.assertEqual(self.db.get_active_task(self.uid), before)
            self.assertEqual(self.complete()['task']['current_step'], '旧C')


class ForestValidationTests(unittest.TestCase):
    def test_invalid_model_structures_fail_without_fallback(self):
        invalid = [None, {}, {'trees': []}, {'trees': ['x']}, {'trees': [{'text': '重', 'children': []}]},
                   {'trees': [{'text': '重', 'children': [{'text': '中', 'children': [None]}]}]},
                   {'trees': [{'text': '重', 'children': [{'text': '中', 'children': [{'text': ' '}]}]}]},
                   {'fine': ['细'], 'normal': ['中'], 'coarse': ['重']}]
        adapter = OpenAICompatLLM(Settings())
        for bad in invalid:
            with self.subTest(data=bad):
                with self.assertRaises(ValueError): task_forest.validate_blueprint(bad)
                with patch.object(adapter, '_chat', return_value=json.dumps(bad)):
                    with self.assertRaises(AIError):
                        adapter.decompose('写论文')

    def test_depth_text_node_and_branch_limits_and_duplicate_ownership(self):
        too_deep = example(); too_deep['trees'][0]['children'][0]['children'][0]['children'] = [{'text': 'extra'}]
        too_wide = {'trees': example()['trees'] * 22}
        too_long = example(); too_long['trees'][0]['text'] = 'x' * 501
        too_many = {'trees': [{'text': '重', 'children': [{'text': '中', 'children': [{'text': '轻'}] * 64}] * 16}]}
        for bad in (too_deep, too_wide, too_long, too_many):
            with self.assertRaises(ValueError): task_forest.validate_blueprint(bad)
        levels = task_forest.new_plan(example()); plan = levels[task_forest.KEY]
        first = plan['roots'][0]; plan['nodes'][first]['children'].append(plan['nodes'][first]['children'][0])
        with self.assertRaises(ValueError): task_forest.read({'levels_json': json.dumps(levels), 'level': 2})

    def test_variable_shapes_random_switches_complete_every_leaf_once(self):
        rng = random.Random(20261107)
        for _ in range(40):
            trees = []
            for root in range(rng.randint(1, 4)):
                mids = []
                for medium in range(rng.randint(1, 4)):
                    mids.append({'text': f'中{root}-{medium}', 'children': [
                        {'text': f'轻{root}-{medium}-{leaf}'} for leaf in range(rng.randint(1, 5))]})
                trees.append({'text': f'重{root}', 'children': mids})
            plan = task_forest.new_plan({'trees': trees})[task_forest.KEY]
            all_leaves = set(task_forest.all_leaf_ids(plan)); consumed = set()
            for turn in range(len(all_leaves) + 1):
                before = list(plan['completed_leaf_ids'])
                for _ in range(rng.randint(0, 8)):
                    task_forest.resize(plan, rng.choice(['smaller', 'bigger']))
                    self.assertEqual(plan['completed_leaf_ids'], before)
                batch = set(task_forest.remaining(plan, plan['current_node_id']))
                self.assertTrue(batch); self.assertFalse(consumed & batch)
                consumed |= batch
                if task_forest.complete(plan): break
            self.assertEqual(consumed, all_leaves)
            self.assertEqual(set(plan['completed_leaf_ids']), all_leaves)

    def test_fixture_handles_long_goals_and_large_numeric_counts_within_limits(self):
        for title in ('一个未归类的目标' * 200, '背' + '9' * 5000 + '个单词'):
            levels = task_forest.new_plan(decompose_forest(title))
            plan = task_forest.read({'levels_json': json.dumps(levels), 'level': 2})
            self.assertTrue(task_forest.view(plan)['current_step'])

    def test_isolated_fixtures_are_valid_forests_and_quantity_ranges_are_disjoint(self):
        for title in ['写论文', '背50个单词', '阅读', '写代码', '运动', '收拾房间', '做件小事']:
            plan = task_forest.new_plan(decompose_forest(title))[task_forest.KEY]
            self.assertTrue(task_forest.all_leaf_ids(plan))
        plan = task_forest.new_plan(decompose_forest('背50个单词'))[task_forest.KEY]
        texts = [plan['nodes'][leaf]['text'] for leaf in task_forest.all_leaf_ids(plan)]
        self.assertEqual(sum(text.startswith('读第') for text in texts), 50)
        self.assertEqual(len(texts), len(set(texts)))


if __name__ == '__main__':
    unittest.main()
