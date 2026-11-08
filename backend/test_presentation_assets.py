import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4
from fastapi.testclient import TestClient
from app import memo, presentation, task_forest
from app.db import DB
from app.main import app
from test_memo import Fake


def many():
    return {'trees':[{'text':'第一段','children':[{'text':f'动作{i}','children':[{'text':f'轻动作{i}'}]} for i in range(1,21)]}]}


class PresentationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.db=DB(str(Path(self.tmp.name)/'test.db'));self.ai=Fake()
        self.ai.decompose=lambda goal:many();self.uid='u'
    def tearDown(self):self.tmp.cleanup()
    def op(self,action,key=None,**kw):return memo.execute(self.db,self.ai,self.uid,key or uuid4().hex,dict(action=action,**kw))
    def state(self):return memo.view(memo.load(self.db,self.uid))
    def start(self):
        r=self.op('intake',text='三个任务');return self.op('select',item_id=r['items'][0]['id'])
    def complete(self,key=None):
        f=self.state()['focus'];return self.op('complete',key=key,session_id=f['session_id'],step_id=f['step']['step_id'])
    def test_all_twelve_steps_and_cap_mapping(self):
        stages=['initial']*3+['starting']*3+['flow']*3+['reward']*3
        for number in range(1,17):
            p=presentation.for_steps(number-1)
            index=min(number,12)-1
            self.assertEqual(p['step_number'],number);self.assertEqual(p['normal_stage'],stages[index])
            self.assertEqual(p['receipt']['id'],f'{index//3+1}.{index%3+1}')
    def test_step_two_interrupt_uses_one_two_without_completing_step_two(self):
        r=self.start();self.complete();before=self.state()['focus'];p=before['presentation']
        self.assertEqual(p['step_number'],2);self.assertEqual(p['receipt']['id'],'1.2')
        r=self.op('end',session_id=before['session_id']);receipt=r['events'][0]
        self.assertEqual(receipt['outcome'],'interrupted');self.assertEqual(receipt['presentation'],p)
        self.assertEqual(len(r['items'][0]['progress']['completed_leaf_ids']),1)
        self.assertIn('轻动作2',r['items'][0]['progress']['remaining_actions'])
        r=self.op('select',item_id=r['items'][0]['id'])
        self.assertEqual(r['focus']['presentation']['step_number'],2)
    def test_third_to_fourth_changes_stage_only_after_completion(self):
        self.start();self.complete();r=self.complete()
        self.assertEqual(r['focus']['presentation']['receipt']['id'],'1.3')
        r=self.complete();self.assertEqual(r['focus']['presentation']['normal_stage'],'starting')
        self.assertEqual(r['focus']['presentation']['receipt']['id'],'2.1')
    def test_heavy_completion_counts_one_and_updates_all_covered_leaves(self):
        self.start();f=self.state()['focus'];self.op('resize',session_id=f['session_id'],step_id=f['step']['step_id'],direction='bigger')
        r=self.complete();receipt=r['events'][0]
        self.assertEqual(receipt['presentation']['step_number'],1)
        self.assertEqual(receipt['presentation']['completed_steps'],1)
        self.assertEqual(receipt['presentation']['receipt']['id'],'1.1')
        self.assertEqual(len(receipt['completed_leaf_ids']),20)
    def test_resize_does_not_count_or_change_completed_leaves(self):
        self.start();before=self.state()['focus']
        for direction in ('bigger','smaller','smaller','bigger','smaller'):
            f=self.state()['focus'];r=self.op('resize',session_id=f['session_id'],step_id=f['step']['step_id'],direction=direction)
            self.assertEqual(r['focus']['presentation'],before['presentation'])
            self.assertEqual(r['focus']['progress']['completed_leaf_ids'],[])
    def test_finish_uses_last_step_without_increment(self):
        self.start()
        for _ in range(20):r=self.complete()
        p=r['events'][0]['presentation'];self.assertEqual(p['step_number'],20)
        self.assertEqual(p['receipt']['id'],'4.3');self.assertEqual(p['normal_stage'],'reward')
    def test_independent_tasks_resume_and_restart_database(self):
        self.start();self.complete();self.complete();f=self.state()['focus'];self.op('end',session_id=f['session_id'])
        ids=[i['id'] for i in self.state()['items']]
        r=self.op('select',item_id=ids[1]);self.assertEqual(r['focus']['presentation']['step_number'],1)
        self.complete();f=self.state()['focus'];self.op('end',session_id=f['session_id'])
        self.db=DB(self.db.path);r=self.op('select',item_id=ids[0]);self.assertEqual(r['focus']['presentation']['step_number'],3)
        f=r['focus'];self.op('end',session_id=f['session_id']);r=self.op('select',item_id=ids[2])
        self.assertEqual(r['focus']['presentation']['step_number'],1)
    def test_duplicate_or_stale_complete_does_not_increment(self):
        r=self.start();f=r['focus'];cmd=dict(session_id=f['session_id'],step_id=f['step']['step_id'])
        first=self.op('complete',key='same',**cmd);again=self.op('complete',key='same',**cmd)
        self.assertEqual(first,again)
        with self.assertRaises(Exception):self.op('complete',**cmd)
        self.assertEqual(self.state()['focus']['presentation']['step_number'],2)
    def test_interruption_retry_keeps_frozen_receipt_image(self):
        self.start();self.complete();f=self.state()['focus'];r=self.op('end',key='end',session_id=f['session_id'])
        self.assertEqual(self.op('end',key='end',session_id=f['session_id']),r)
        self.assertEqual(len(r['events']),1);self.assertEqual(r['events'][0]['presentation']['receipt']['id'],'1.2')
    def test_legacy_count_backfilled_from_completion_operations_not_leaves(self):
        self.start();self.complete();self.complete()
        with self.db._conn() as c:
            state=json.loads(c.execute('SELECT data FROM memo_state').fetchone()[0])
            for i in state['days'][memo.today()]['items']:i.pop('presentation_completed_steps',None)
            c.execute('UPDATE memo_state SET data=?',(json.dumps(state),))
        self.assertEqual(self.state()['focus']['presentation']['step_number'],3)
        self.assertEqual(self.state()['focus']['presentation']['source'],'operation_history')
    def test_old_heavy_completion_is_one_operation_even_with_many_done_leaves(self):
        first=many()['trees'][0];self.ai.decompose=lambda goal:{'trees':[first,{'text':'下一段','children':[{'text':'下一步','children':[{'text':'最后动作'}]}]}]}
        self.start();f=self.state()['focus'];self.op('resize',session_id=f['session_id'],step_id=f['step']['step_id'],direction='bigger')
        self.complete()
        with self.db._conn() as c:
            state=json.loads(c.execute('SELECT data FROM memo_state').fetchone()[0])
            for i in state['days'][memo.today()]['items']:i.pop('presentation_completed_steps',None)
            c.execute('UPDATE memo_state SET data=?',(json.dumps(state),))
        r=self.state();self.assertEqual(len(r['focus']['progress']['completed_leaf_ids']),20)
        self.assertEqual(r['focus']['presentation']['step_number'],2)

    def test_failed_commit_rolls_back_presentation_counter_and_retry_counts_once(self):
        from contextlib import contextmanager
        import sqlite3
        self.start();f=self.state()['focus'];original=self.db._conn;count=0
        @contextmanager
        def fail_commit():
            nonlocal count
            count+=1
            with original() as c:
                yield c
                if count==2:raise sqlite3.OperationalError('isolated commit failure')
        with patch.object(self.db,'_conn',fail_commit),self.assertRaises(sqlite3.OperationalError):
            self.op('complete',key='retry-fail',session_id=f['session_id'],step_id=f['step']['step_id'])
        self.assertEqual(self.state()['focus']['presentation']['step_number'],1)
        r=self.op('complete',key='retry-fail',session_id=f['session_id'],step_id=f['step']['step_id'])
        self.assertEqual(r['focus']['presentation']['step_number'],2)

    def test_unrecoverable_old_count_does_not_guess_from_leaves(self):
        self.start();self.complete()
        with self.db._conn() as c:
            state=json.loads(c.execute('SELECT data FROM memo_state').fetchone()[0])
            for i in state['days'][memo.today()]['items']:i.pop('presentation_completed_steps',None)
            c.execute('UPDATE memo_state SET data=?',(json.dumps(state),));c.execute('DELETE FROM memo_operations')
        r=self.state();self.assertFalse(r['focus']['presentation']['available'])
        self.assertIsNone(r['focus']['presentation']['receipt']);self.assertEqual(len(r['focus']['progress']['completed_leaf_ids']),1)
        self.complete();self.assertEqual(len(self.state()['focus']['progress']['completed_leaf_ids']),2)
    def test_idle_policy_is_local_and_does_not_create_progress_commands(self):
        self.start();before=memo.load(self.db,self.uid)
        policy=presentation.catalogue()['idle_policy']
        self.assertEqual(policy['timeout_seconds'],300);self.assertTrue(policy['foreground_only'])
        self.assertEqual(policy['effect'],'pet_image_only');self.assertEqual(policy['single_tap'],'none')
        self.assertEqual(policy['double_tap'],'add_tasks_dialog')
        self.assertEqual(memo.load(self.db,self.uid),before)
    def test_receipt_date_is_actual_date_not_task_ownership_day(self):
        with patch('app.memo.today',return_value='2026-11-07'):self.start()
        with patch('app.memo.today',return_value='2026-11-08'):
            f=self.state()['focus'];r=self.op('end',session_id=f['session_id'])
        self.assertEqual(r['events'][0]['date'],'2026-11-07');self.assertEqual(r['events'][0]['occurred_date'],'2026-11-08')


class AssetHTTPTests(unittest.TestCase):
    def test_all_runtime_assets_are_accessible_hash_correct_and_png_alpha_preserved(self):
        with TestClient(app) as client:
            result=client.get('/api/assets/manifest');self.assertEqual(result.status_code,200);m=result.json()
            assets=list(m['pets'].values())+list(m['receipts'].values())+[r['preview'] for r in m['receipts'].values()]
            for asset in assets:
                r=client.get(asset['url']);self.assertEqual(r.status_code,200,asset['url'])
                self.assertEqual(hashlib.sha256(r.content).hexdigest(),asset['sha256'])
                self.assertEqual(len(r.content),asset['bytes']);self.assertIn('immutable',r.headers['cache-control'])
            for pet in m['pets'].values():
                data=client.get(pet['url']).content
                self.assertEqual(data[:8],b'\x89PNG\r\n\x1a\n');self.assertEqual(data[25],6) # RGBA
                self.assertLessEqual(struct.unpack('>II',data[16:24])[0],512)
    def test_unprovided_journal_and_emergency_trigger_are_not_invented(self):
        m=presentation.catalogue();self.assertFalse(m['journal']['available']);self.assertIsNone(m['journal']['background'])
        self.assertFalse(m['pets']['emergency_dark']['automatic_trigger'])
        self.assertEqual({presentation.for_steps(n)['normal_stage'] for n in range(15)},set(presentation.STAGES))
    def test_original_archives_not_public_and_missing_image_does_not_break_task_routes(self):
        with TestClient(app) as client:
            self.assertEqual(client.get('/api/assets/v1/../originals/states.zip').status_code,404)
            self.assertEqual(client.get('/api/assets/v1/receipts/missing.jpg').status_code,404)
            self.assertEqual(client.get('/api/health').status_code,200)
    def test_receipt_manifest_has_per_image_source_and_date_text_composition(self):
        m=presentation.catalogue();self.assertEqual(len(m['receipts']),12)
        for key,asset in m['receipts'].items():
            self.assertTrue(asset['source'].split('/')[1].startswith(key))
            cfg=asset['composition'];self.assertTrue(cfg['baked_date'])
            self.assertEqual(cfg['preview_and_export'],'same_canvas_composition')
            self.assertIn('never_clip',cfg['overflow']);self.assertEqual(cfg['date_source'],'receipt_event.occurred_date')


class SuppliedSourceTests(unittest.TestCase):
    def verify_original(self, name, assets):
        import zipfile
        meta=presentation.MANIFEST['originals'][name]
        raw=(presentation.ASSET_ROOT/'originals'/name).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),meta['sha256'])
        with zipfile.ZipFile(presentation.ASSET_ROOT/'originals'/name) as z:
            for asset in assets:self.assertEqual(hashlib.sha256(z.read(asset['source'])).hexdigest(),asset['source_sha256'])
    def test_original_state_archive_is_byte_identical(self):
        self.verify_original('states.zip',presentation.MANIFEST['pets'].values())
    @unittest.skipUnless((presentation.ASSET_ROOT/'originals/receipts.zip').exists(),
                         'Original receipt ZIP is a separately delivered build input; runtime derivatives are tested independently.')
    def test_supplied_receipt_archive_is_byte_identical_when_available(self):
        self.verify_original('receipts.zip',presentation.MANIFEST['receipts'].values())
    def test_date_masks_cover_measured_fixed_dates_without_entering_text_area(self):
        # Bounds measured/OCR-checked against the supplied artwork, including the higher 4.2 date.
        bounds={'1.1':(1270,2323,180,28),'1.2':(1264,2328,159,27),'1.3':(1249,2325,162,29),
                '2.1':(1263,2299,168,27),'2.2':(1186,2328,235,36),'2.3':(1261,2320,182,29),
                '3.1':(1224,2293,184,29),'3.2':(1245,2332,170,27),'3.3':(1070,2280,310,45),
                '4.1':(1227,2293,177,29),'4.2':(1215,2262,170,27),'4.3':(1252,2326,192,30)}
        for key,(x,y,w,h) in bounds.items():
            cfg=presentation.MANIFEST['receipts'][key]['composition'];rect=cfg['date_cover'];text=cfg['text_box']
            self.assertLessEqual(rect['x'],x);self.assertLessEqual(rect['y'],y)
            self.assertGreaterEqual(rect['x']+rect['width'],x+w);self.assertGreaterEqual(rect['y']+rect['height'],y+h)
            self.assertLessEqual(text['y']+text['height'],rect['y'])
