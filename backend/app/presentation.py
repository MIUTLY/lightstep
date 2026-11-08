"""Public asset catalogue and per-task presentation steps, independent of leaf progress."""
import copy
import json
from pathlib import Path

ASSET_ROOT = Path(__file__).resolve().parents[1] / 'assets'
MANIFEST = json.loads((ASSET_ROOT/'manifest.json').read_text())
STAGES = ('initial','starting','flow','reward')


def catalogue():
    result=copy.deepcopy(MANIFEST)
    result.pop('originals',None)
    result['idle_policy']={'foreground_only':True,'timeout_seconds':300,
        'reset_on':['touch','input','click','foreground'], 'on_background':'cancel',
        'effect':'pet_image_only','idle_pet':copy.deepcopy(MANIFEST['pets']['distracted']),
        'single_tap':'none','double_tap':'add_tasks_dialog', 'changes_progress':False}
    result['receipt_selection']='current_step_on_interrupt_last_completed_on_finish_capped_at_12'
    return result


def for_steps(completed, *, finished=False, source='recorded'):
    if completed is None:
        return {'available':False,'completed_steps':None,'step_number':None,
                'normal_stage':None,'normal_pet':None,'receipt':None,
                'source':'legacy_count_unavailable'}
    number=max(1,completed) if finished else completed+1
    index=min(number,12)-1
    key=f'{index//3+1}.{index%3+1}'
    stage=STAGES[index//3]
    return {'available':True,'completed_steps':completed,'step_number':number,
            'normal_stage':stage,'normal_pet':copy.deepcopy(MANIFEST['pets'][stage]),
            'receipt':dict(copy.deepcopy(MANIFEST['receipts'][key]),id=key),
            'source':source,'asset_version':MANIFEST['version']}
