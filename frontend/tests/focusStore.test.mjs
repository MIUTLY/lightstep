import test from 'node:test'
import assert from 'node:assert/strict'
import { loadFrontend } from './helpers/runtime.mjs'
async function setup() {
 const disk=new Map(), calls=[];let fail=false, answer
 const uni={getStorageSync:k=>disk.get(k),setStorageSync:(k,v)=>disk.set(k,v)}
 const api={today:async()=>({revision:1,date:'2026-11-08',items:[{id:'a'}],focus:{session_id:'s',step:{step_id:'p1'}}}),
  todayCommand:async payload=>{calls.push(payload);if(fail)throw Error('offline');return answer || {revision:2,items:[{id:'a'}],focus:{session_id:'s',step:{step_id:'p2'}},operation:{status:'succeeded'}}},
  focusCapture:async()=>({revision:2,capture:{saved:true},operation:{status:'succeeded'}})}
 const ns=await loadFrontend('store/today.js',{mocks:{vue:{reactive:x=>x},'./user.js':{useUser:()=>({current:()=> 'u'})},'@/api/index.js':api},globals:{uni}})
 const today=ns.useToday();await today.load()
 return {today,calls,disk,setFail:v=>{fail=v},setAnswer:v=>{answer=v}}
}
test('完成丢响应后重试复用request_id，下一步使用新的ID',async()=>{
 const {today,calls,setFail}=await setup();setFail(true);await today.complete();setFail(false);await today.complete()
 assert.equal(calls[0].request_id,calls[1].request_id);assert.equal(today.focus.step.step_id,'p2')
 await today.complete();assert.notEqual(calls[1].request_id,calls[2].request_id)
})
test('结束断网不清空专注，重试复用ID',async()=>{
 const {today,calls,setFail,setAnswer}=await setup();setFail(true);await today.end();assert.equal(today.focus.session_id,'s')
 setFail(false);setAnswer({revision:2,items:[{id:'a'}],focus:null,operation:{status:'succeeded'}});await today.end()
 assert.equal(today.focus,null);assert.equal(calls[0].request_id,calls[1].request_id)
})
test('切下一项丢响应重试同ID；新一轮选择同项使用新ID',async()=>{
 const {today,calls,setFail,setAnswer}=await setup();setFail(true);await today.select('b');setFail(false)
 await today.select('b');assert.equal(calls[0].request_id,calls[1].request_id)
 setAnswer({revision:3,items:[],focus:null,operation:{status:'succeeded'}});await today.end();await today.select('b')
 assert.notEqual(calls[1].request_id,calls[3].request_id)
})
test('桌宠紧凑响应不清空专注或任务清单',async()=>{
 const {today}=await setup();await today.capture('买菜')
 assert.equal(today.focus.session_id,'s');assert.equal(today.items[0].id,'a')
})
test('ack失败不把事件标为已处理',async()=>{
 const {today,setFail}=await setup();setFail(true);await today.ack('receipt')
 assert.equal(today.isAcked('receipt'),false)
})
