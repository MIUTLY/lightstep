import test from 'node:test'
import assert from 'node:assert/strict'
import { loadFrontend, deferred } from './helpers/runtime.mjs'
function storage() { const data=new Map(); return { getStorageSync:k=>data.get(k),setStorageSync:(k,v)=>data.set(k,v),data } }
function view(focus,events=[],next='') { return {focus,events,date:'2026-11-08',suggested_item_id:next,operation:{status:'succeeded'}} }
async function setup() {
 const disk=storage(), mod=await loadFrontend('utils/focusFlow.js',{globals:{uni:disk}})
 const today={busy:false,date:'2026-11-08',focus:{session_id:'A'},events:[]}
 const apply=r=>{today.focus=r.focus;today.events=r.events;return r}
 today.complete=async()=>apply(view(null,[{kind:'receipt',id:'a',title:'A',outcome:'completed'}],'b'))
 today.select=async id=>apply(view({session_id:id,step:{step_id:id+':first'}},today.events))
 today.end=async()=>apply(view(null,[...today.events,{kind:'receipt',id:'b',title:'B',outcome:'interrupted'}]))
 return {disk,mod,today,apply,flow:mod.createFocusFlow({today,userId:()=> 'u',storage:disk})}
}
test('完成A自动选择B，使用B的新步骤而非A的位置；不弹中途回执',async()=>{
 const {flow,today}=await setup();assert.equal((await flow.complete()).status,'executing')
 assert.equal(today.focus.step.step_id,'b:first');assert.equal(flow.pending(),null)
})
test('最后一项完成结束本轮，合并事实并只排队一张回执',async()=>{
 const {flow,today,apply}=await setup();await flow.complete()
 today.complete=async()=>apply(view(null,[{kind:'receipt',id:'a',title:'A',outcome:'completed'},{kind:'receipt',id:'b',title:'B',outcome:'completed'}]))
 assert.equal((await flow.complete()).status,'finished');const r=flow.pending();assert.deepEqual(Array.from(r.receipts,e=>e.id),['a','b'])
 flow.recover(today.events,false);assert.equal(flow.pending().id,r.id);assert.equal(flow.pending().receipts.length,2)
})
test('退出成功后才结束轮次；失败保持专注且没有假回执',async()=>{
 const {flow,today}=await setup();today.end=async()=>null
 assert.equal((await flow.end()).status,'failed');assert.equal(today.focus.session_id,'A');assert.equal(flow.pending(),null)
})
test('中途退出排队回执，不自动新开任务，草稿和事件可重开恢复',async()=>{
 const {flow,today,disk,mod}=await setup();assert.equal((await flow.end()).status,'finished');assert.equal(today.focus,null)
 const id=flow.pending().id;flow.patch(id,{draft:'下次接着做'})
 const reopened=mod.createFocusFlow({today,userId:()=> 'u',storage:disk});assert.equal(reopened.pending().draft,'下次接着做')
 assert.equal(reopened.pending().receipts[0].outcome,'interrupted')
})
test('B生成失败不回滚A，重试只选B，不再次完成A',async()=>{
 const {flow,today}=await setup();let completes=0;const old=today.complete;today.complete=async()=>{completes++;return old()}
 today.select=async()=>null;assert.equal((await flow.complete()).status,'next_failed')
 today.select=async()=>{today.focus={session_id:'B'};return view(today.focus,today.events)}
 assert.equal((await flow.retryNext('b')).status,'executing');assert.equal(completes,1)
})
test('切下一项失败时用户仍可结束并带上已完成A的回执',async()=>{
 const {flow,today}=await setup();today.select=async()=>null;await flow.complete()
 assert.equal((await flow.end()).status,'finished');assert.equal(flow.pending().receipts[0].id,'a');assert.equal(flow.pending().outcome,'interrupted')
})
test('下一项需要澄清时回对话页，不留空壳专注',async()=>{
 const {flow,today}=await setup();today.select=async()=>({focus:null,operation:{status:'needs_clarification'}})
 assert.equal((await flow.complete()).status,'clarification');assert.ok(flow.pending())
})
test('连续点击只发送一次完成请求',async()=>{
 const {flow,today,apply}=await setup();const pending=deferred();let count=0
 today.complete=async()=>{count++;return apply(await pending.promise)}
 const first=flow.complete();assert.equal((await flow.complete()).status,'busy')
 pending.resolve(view({session_id:'A',step:{step_id:'A:next'}}));await first;assert.equal(count,1)
})
test('不同用户不共享回执和草稿',async()=>{
 const {flow,today,disk,mod}=await setup();await flow.end()
 assert.equal(mod.createFocusFlow({today,userId:()=> 'other',storage:disk}).pending(),null)
})
test('清单日期切换不自动开始另一日任务',async()=>{
 const {flow,today,apply}=await setup();today.complete=async()=>apply({...view(null,[{id:'a',kind:'receipt'}],'old-task'),date:'2026-11-07'})
 assert.equal((await flow.complete()).status,'finished')
})

test('旧回执暂存后，新一轮结束优先显示本轮而不是旧回执',async()=>{
 const {flow,today,apply}=await setup();await flow.end();const old=flow.pending();flow.patch(old.id,{deferred:true})
 today.focus={session_id:'new'};today.events=[];flow.begin()
 today.end=async()=>apply(view(null,[{kind:'receipt',id:'new-receipt',title:'新任务',outcome:'interrupted'}]))
 await flow.end();assert.notEqual(flow.pending().id,old.id);assert.equal(flow.pending().receipts[0].id,'new-receipt')
})
