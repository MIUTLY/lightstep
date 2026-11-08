"""Add-only focus input. No access to task completion, exit or replacement dispatch."""
import copy
from uuid import uuid4
from fastapi import HTTPException
from . import memo
from .llm import Clarification


def response(state, request_id, status, capture):
    return {'revision':state['revision'], 'operation':{'request_id':request_id,'status':status},
            'capture':capture, 'reply':capture.get('feedback') or capture.get('question','')}


def prepare(c, uid, request_id, cmd, state):
    context = {'batch_id':request_id,'original_input':cmd['text'],'answers':[]}
    parent = cmd.get('parent_request_id')
    if parent:
        import json
        row = c.execute('SELECT payload,response FROM memo_operations WHERE user_id=? AND request_id=?',(uid,parent)).fetchone()
        if not row or not row['response']:
            raise HTTPException(409,'澄清请求不存在或尚未完成。')
        old_cmd, result = json.loads(row['payload']), json.loads(row['response'])
        if old_cmd['action']!='focus_capture' or old_cmd['session_id']!=cmd['session_id'] or old_cmd['text']!=cmd['text']:
            raise HTTPException(409,'澄清与原输入或专注会话不匹配。')
        if result['operation']['status']=='succeeded' and result.get('capture',{}).get('saved'):
            cmd['_capture_context'] = dict(context,batch_id=result['capture']['batch_id'])
            return
        if result['operation']['status']!='needs_clarification':
            raise HTTPException(409,'该请求没有待回答的澄清。')
        context = copy.deepcopy(result['capture']['context'])
        if cmd.get('anchor_id'):
            choices = result['capture'].get('choices',[])
            if cmd['anchor_id'] not in {x['id'] for x in choices}:
                raise HTTPException(422,'请选择澄清中列出的任务。')
            context['confirmed_anchor_id'] = cmd['anchor_id']
            context['proposal'] = result['capture']['proposal']
        elif cmd.get('answer'):
            context['answers'].append({'question':result['capture']['question'],'answer':cmd['answer']})
        else:
            raise HTTPException(422,'请提供澄清回答或选定任务。')
    elif cmd.get('answer') or cmd.get('anchor_id'):
        raise HTTPException(422,'回答必须关联原澄清请求。')
    cmd['_capture_context'] = context


def apply(state, ai, cmd):
    ctx=cmd['_capture_context']
    saved=state.get('capture_batches',{}).get(ctx['batch_id'])
    if saved:
        return 'succeeded', copy.deepcopy(saved)
    active=state['active']
    if not active or active['session_id']!=cmd['session_id']:
        raise HTTPException(409,'当前专注已结束或变化，输入已保留，请回到当前任务后处理。')
    date, current = memo.find(state,active['item_id'])
    items=state['days'][date]['items']
    context={'original_input':ctx['original_input'],'answers':ctx['answers'],
             'current_task':{'id':current['id'],'title':current['title']},
             'tasks':[{'id':i['id'],'title':i['title']} for i in items]}
    try:
        proposal=ctx.get('proposal') if ctx.get('confirmed_anchor_id') else ai.extract_focus_tasks(context)
    except Clarification as error:
        return 'needs_clarification', {'saved':False,'question':error.question,'context':ctx,'choices':[]}
    titles, placement = proposal['tasks'], proposal['placement']
    anchor = None
    if ctx.get('confirmed_anchor_id'):
        anchor = next((i for i in items if i['id']==ctx['confirmed_anchor_id']),None)
        if not anchor: raise HTTPException(409,'所选位置已变化，请刷新后重新澄清。')
    elif placement['kind']=='after_current':
        anchor = current
    elif placement['kind']=='after_named':
        matches=[i for i in items if i['title']==placement['target']]
        if len(matches)!=1:
            question = (f"有多个「{placement['target']}」，要放在哪一项后面？" if matches else
                        f"没有找到「{placement['target']}」，要放在现有哪项后面，还是放到最后？")
            return 'needs_clarification', {'saved':False,'question':question,'context':ctx,'proposal':proposal,
                'choices':[{'id':i['id'],'title':i['title'],'position':items.index(i)+1} for i in matches]}
        anchor=matches[0]
    index = items.index(anchor)+1 if anchor else len(items)
    added=[{'id':uuid4().hex,'title':t,'original_input':ctx['original_input'],
            'completed':False,'presentation_completed_steps':0,'scope':None,'question':None,'answers':[],'plan':None} for t in titles]
    items[index:index]=added
    result={'saved':True,'batch_id':ctx['batch_id'],'added_item_ids':[i['id'] for i in added],
            'count':len(added),'date':date,'after_item_id':anchor['id'] if anchor else None,
            'feedback':(f"收到，放在{anchor['title']}后面。" if len(anchor['title'])<=20 else '收到，放到指定任务后面啦。') if anchor else '收到，放到最后啦。'}
    state.setdefault('capture_batches',{})[ctx['batch_id']]=copy.deepcopy(result)
    return 'succeeded',result
