"""Persistent outer task list. Forest transitions reuse task_forest; no task templates."""
import copy
import json
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from . import task_forest
from .llm import AIError, Clarification, invalid_response, AI_DEADLINE
from time import monotonic


def today():
    return datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()


def empty():
    return {'revision': 0, 'days': {}, 'active': None, 'events': []}


def retain_unfinished(state):
    """Upgrade old completed rows to minimal receipt/journal facts, without a task forest."""
    for day in state['days'].values():
        finished = day.setdefault('finished', [])
        known = {item['id'] for item in finished}
        for item in day['items']:
            if item['completed'] and item['id'] not in known:
                finished.append({k: item.get(k) for k in ('id', 'title', 'scope')})
                known.add(item['id'])
        day['items'] = [item for item in day['items'] if not item['completed']]
    return state


def day_completed(day):
    # An untouched empty day is not a completed day.
    return bool(day.get('finished')) and not day['items']


def load(db, uid):
    with db._conn() as c:
        row = c.execute('SELECT data FROM memo_state WHERE user_id=?', (uid,)).fetchone()
        return retain_unfinished(json.loads(row[0])) if row else empty()


def view(state, date=None):
    state = retain_unfinished(copy.deepcopy(state))
    current_date = today()
    available_dates = sorted((d for d, day in state['days'].items() if day['items']), reverse=True)
    if date is None:
        # Keep the focused list visible across midnight; otherwise reopen the latest saved list.
        date = (find(state, state['active']['item_id'])[0] if state['active'] else
                current_date if current_date in available_dates else
                available_dates[0] if available_dates else current_date)
    day = state['days'].get(date, {'items': []})
    items = []
    for item in day['items']:
        row = {k: v for k, v in item.items() if k != 'plan'}
        plan = item.get('plan')
        row['progress'] = progress(plan)
        row['step'] = task_forest.view(plan) if plan and plan['current_node_id'] else None
        items.append(row)
    first = next((i for i in items if not i['completed']), None)
    active = state['active']
    active_item = None
    if active:
        i = find(state, active['item_id'])[1]
        active_item = dict(active, title=i['title'], scope=i['scope'], progress=progress(i['plan']), step=task_forest.view(i['plan']))
    return {'navigation': {'sidebar_locked': bool(active), 'can_collapse_focus': not bool(active)},
            'state': 'executing' if active else 'memo', 'revision': state['revision'], 'date': date,
            'today_date': current_date, 'available_dates': available_dates,
            'today_all_completed': day_completed(state['days'].get(current_date, {'items':[]})),
            'items': items, 'focus': active_item,
            'clarifications': pending_items(state),
            'can_enter_focus': not bool(pending_items(state)) and not bool(active),
            'all_completed': day_completed(day),
            'suggested_item_id': first['id'] if first else None,
            'reply': (pending_items(state)[0]['question'] if pending_items(state) and not active else
                      f"我们是否从【{first['title']}】开始？" if first and not active else ''),
            'events': [e for e in state['events'] if not e['acknowledged']]}


def progress(plan):
    if not plan:
        return {'completed_leaf_ids': [], 'remaining_leaf_ids': [], 'generated': False}
    leaves = task_forest.all_leaf_ids(plan)
    done = plan['completed_leaf_ids']
    return {'generated': True, 'completed_leaf_ids': done,
            'remaining_leaf_ids': [n for n in leaves if n not in done],
            'completed_actions': [plan['nodes'][n]['text'] for n in done],
            'remaining_actions': [plan['nodes'][n]['text'] for n in leaves if n not in done]}


def find(state, item_id):
    for date, day in state['days'].items():
        for item in day['items']:
            if item['id'] == item_id:
                return date, item
    raise HTTPException(404, '备忘录任务不存在。')


def event(state, kind, **facts):
    state['events'].append(dict(id=uuid4().hex, revision=state['revision']+1, kind=kind, acknowledged=False, **facts))


def end_focus(state, date, item, completed):
    active = state['active']
    plan = item['plan']
    facts = progress(plan)
    facts['session_completed_leaf_ids'] = [n for n in plan['completed_leaf_ids'] if n not in active['initial_done']]
    facts['session_completed_actions'] = [plan['nodes'][n]['text'] for n in facts['session_completed_leaf_ids']]
    event(state, 'receipt', item_id=item['id'], title=item['title'], scope=item['scope'], date=date,
          session_id=active['session_id'], outcome='completed' if completed else 'interrupted', **facts)
    state['active'] = None
    retain_unfinished(state)
    day = state['days'][date]
    if day_completed(day):
        if day.get('journal_event_id'):
            prior = next(e for e in state['events'] if e['id']==day['journal_event_id'])
            prior.update(eligible=True, acknowledged=False, revision=state['revision']+1, item_ids=[i['id'] for i in day['finished']],
                         tasks=[{'id':i['id'], 'title':i['title'], 'scope':i['scope']} for i in day['finished']])
            return
        event(state, 'daily_journal', eligible=True, date=date, item_ids=[i['id'] for i in day['finished']],
              tasks=[{'id': i['id'], 'title': i['title'], 'scope': i['scope']} for i in day['finished']])
        day['journal_event_id'] = state['events'][-1]['id']


def execute(db, ai, uid, request_id, command):
    """Reserve request before AI; compare revision and attempt before atomic save/event creation."""
    attempt = uuid4().hex
    with db._conn() as c:
        c.execute('BEGIN IMMEDIATE')
        previous = c.execute('SELECT * FROM memo_operations WHERE user_id=? AND request_id=?', (uid,request_id)).fetchone()
        command = dict(command, _date=json.loads(previous['payload'])['_date'] if previous else today())
        payload = json.dumps(command, ensure_ascii=False, sort_keys=True)
        if previous and previous['payload'] != payload:
            raise HTTPException(409, 'request_id已用于不同操作。')
        row = c.execute('SELECT data FROM memo_state WHERE user_id=?', (uid,)).fetchone()
        state = retain_unfinished(json.loads(row[0])) if row else empty()
        if command['action']=='focus_capture':
            from . import focus_capture
            focus_capture.prepare(c,uid,request_id,command,state)
            saved=state.get('capture_batches',{}).get(command['_capture_context']['batch_id'])
            if saved:
                result = focus_capture.response(state,request_id,'succeeded',saved)
                c.execute('INSERT OR REPLACE INTO memo_operations VALUES(?,?,?,?,?)',
                          (uid,request_id,payload,attempt,json.dumps(result,ensure_ascii=False)))
                return result
        if previous and previous['response']:
            cached = json.loads(previous['response'])
            if cached['operation']['status'] != 'failed':
                return cached
        c.execute('INSERT OR REPLACE INTO memo_operations VALUES(?,?,?,?,NULL)', (uid,request_id,payload,attempt))
        row = c.execute('SELECT data FROM memo_state WHERE user_id=?', (uid,)).fetchone()
        state = retain_unfinished(json.loads(row[0])) if row else empty()
    revision = state['revision']
    original = copy.deepcopy(state)
    try:
        token = AI_DEADLINE.set(monotonic()+getattr(ai, 'timeout', 30))
        try:
            if command['action']=='focus_capture':
                status, capture = focus_capture.apply(state,ai,command)
                reply = ''
            else:
                status, reply = apply(state, ai, command)
        finally:
            AI_DEADLINE.reset(token)
        state['revision'] += 1
        response = focus_capture.response(state,request_id,status,capture) if command['action']=='focus_capture' else view(state)
        if reply: response['reply'] = reply
        response['operation'] = {'request_id': request_id, 'status': status}
    except AIError as error:
        state = original
        response = ({'revision':state['revision'],'capture':{'saved':False}} if command['action']=='focus_capture' else view(state))
        response.update(reply=error.message, operation={'request_id':request_id, 'status':'failed',
                         'error':{'code':error.code, 'message':error.message, 'retryable':True}})
    with db._conn() as c:
        c.execute('BEGIN IMMEDIATE')
        op = c.execute('SELECT attempt FROM memo_operations WHERE user_id=? AND request_id=?', (uid,request_id)).fetchone()
        row = c.execute('SELECT data FROM memo_state WHERE user_id=?', (uid,)).fetchone()
        current = retain_unfinished(json.loads(row[0])) if row else empty()
        if not op or op[0] != attempt or current['revision'] != revision:
            raise HTTPException(409, '任务清单或进度已变化，请刷新后重试，已有数据已保留。')
        if command['action']=='select' and state['active'] and c.execute('SELECT 1 FROM active_task WHERE user_id=?',(uid,)).fetchone():
            raise HTTPException(409, '旧版任务仍存在，请先处理旧任务。')
        c.execute('INSERT OR REPLACE INTO memo_state VALUES (?,?)', (uid,json.dumps(state,ensure_ascii=False)))
        c.execute('UPDATE memo_operations SET response=? WHERE user_id=? AND request_id=?',
                  (json.dumps(response,ensure_ascii=False),uid,request_id))
    return response


def clarify_item(ai, item, answer=None):
    if answer:
        item['answers'].append({'question':item['question'] or '请明确任务范围', 'answer':answer})
    try:
        item['scope'] = ai.resolve_scope(item['title'], item['answers'])
        item['question'] = None
    except Clarification as error:
        item['question'] = error.question


def pending_items(state):
    return [{'id':i['id'], 'title':i['title'], 'question':i['question']}
            for day in state['days'].values() for i in day['items'] if i.get('question')]


def apply(state, ai, cmd):
    action = cmd['action']
    if action == 'chat':
        if state['active']:
            raise HTTPException(409, '专注期间请使用桌宠新增入口，或先明确结束专注。')
        routed = ai.route_message(cmd['text'], pending_items(state))
        if routed['kind'] == 'chat':
            return 'succeeded', routed['reply']
        if routed['kind'] == 'answer':
            item = find(state, routed['item_id'])[1]
            clarify_item(ai, item, cmd['text'])
            pending = pending_items(state)
            return ('needs_clarification', pending[0]['question']) if pending else ('succeeded', routed['reply'])
        status, reply = apply(state, ai, dict(cmd, action='intake'))
        # Clarify every new task in the conversation before offering focus.
        for item in state['days'][cmd['_date']]['items']:
            if not item['scope'] and not item['question']:
                clarify_item(ai, item)
        pending = pending_items(state)
        return ('needs_clarification', pending[0]['question']) if pending else (status, reply)
    if action == 'intake':
        date = cmd['_date']
        titles = ai.extract_tasks(cmd['text'])
        day = state['days'].setdefault(date, {'items': []})
        if day.get('journal_event_id'):
            prior = next(e for e in state['events'] if e['id']==day['journal_event_id'])
            prior['acknowledged'] = False
            prior['eligible'] = False
            prior['revision'] = state['revision']+1
        for title in titles:
            day['items'].append({'id':uuid4().hex, 'title':title, 'original_input':cmd['text'],
                                'completed':False, 'scope':None, 'question':None, 'answers':[], 'plan':None})
    elif action == 'reorder':
        day = state['days'].get(cmd['date'], {'items':[]})
        ids = cmd['item_ids']
        if len(ids) != len(set(ids)) or set(ids) != {i['id'] for i in day['items']}:
            raise HTTPException(422, '排序必须包含该日每项未完成任务且不能重复。')
        if cmd['revision'] != state['revision']:
            raise HTTPException(409, '清单版本已变化，请刷新。')
        mapping = {i['id']:i for i in day['items']}
        day['items'] = [mapping[i] for i in ids]
    elif action == 'select':
        if state['active']:
            raise HTTPException(409, '请先结束当前专注，再选择其他任务。')
        date, item = find(state, cmd['item_id'])
        for day in state['days'].values():
            for candidate in day['items']:
                if not candidate['scope'] and not candidate['question']:
                    clarify_item(ai, candidate)
        unresolved = [i for i in pending_items(state) if i['id'] != item['id'] or not cmd.get('answer')]
        if unresolved:
            return 'needs_clarification', unresolved[0]['question']
        if item['completed']:
            raise HTTPException(409, '该任务已全部完成。')
        if not item['plan']:
            answer = cmd.get('answer')
            if answer:
                item['answers'].append({'question':item['question'] or '请补充完整任务范围', 'answer':answer})
            try:
                scope = item['scope'] if item['scope'] and not answer else ai.resolve_scope(item['title'], item['answers'])
                blueprint = ai.decompose('必须完整覆盖以下约定范围，禁止只生成启动段：' + scope)
                plan = task_forest.new_plan(blueprint)[task_forest.KEY]
            except Clarification as error:
                item['question'] = error.question
                return 'needs_clarification', error.question
            except (ValueError, KeyError, TypeError, RecursionError):
                raise invalid_response() from None
            item.update(scope=scope, plan=plan, question=None)
        state['active'] = {'item_id':item['id'], 'session_id':uuid4().hex,
                           'initial_done':list(item['plan']['completed_leaf_ids'])}
    elif action in ('resize','complete','end'):
        active = state['active']
        if not active or active['session_id'] != cmd['session_id']:
            raise HTTPException(409, '专注已结束或已变化，请刷新。')
        date, item = find(state, active['item_id'])
        plan = item['plan']
        if action != 'end' and task_forest.view(plan)['step_id'] != cmd['step_id']:
            raise HTTPException(409, '步骤已变化，请刷新。')
        if action == 'resize':
            task_forest.resize(plan, cmd['direction'])
        elif action == 'complete':
            if task_forest.complete(plan):
                item['completed'] = True
                end_focus(state,date,item,True)
        else:
            end_focus(state,date,item,False)
    elif action == 'ack':
        found = next((e for e in state['events'] if e['id']==cmd['event_id']), None)
        if not found: raise HTTPException(404, '事件不存在。')
        found['acknowledged'] = True
    else:
        raise HTTPException(422, '未知操作。')
    return 'succeeded', ''


def operation(db, uid, request_id):
    with db._conn() as c:
        row = c.execute('SELECT payload,response FROM memo_operations WHERE user_id=? AND request_id=?', (uid,request_id)).fetchone()
        if not row: raise HTTPException(404, '操作记录不存在。')
        return {'command':json.loads(row[0]), 'result':json.loads(row[1]) if row[1] else None,
                'request_id':request_id}
