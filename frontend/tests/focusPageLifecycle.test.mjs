import test from 'node:test'
import assert from 'node:assert/strict'
import { loadFrontend } from './helpers/runtime.mjs'
async function setup() {
 const callbacks={},nav=[],toasts=[];let result={status:'failed'},pending=null
 const focus={session_id:'s',title:'A',step:{step_id:'first'},progress:{}}
 const today={busy:false,loaded:true,focus,events:[],pendingSelect:null,canEnterFocus:true,
  hasFocus(){return !!this.focus},hasClarifications:()=>false,completedActions:()=>[],focusPresentation:()=>null,policy:()=>null,firstClarification:()=>null}
 const flow={begin:()=>{},pending:()=>pending,recover:()=>{},complete:async()=>result,end:async()=>result,retryNext:async()=>result}
 const ns=await loadFrontend('pages/focusmode/focusmode.vue',{expose:['onDone','onExit','retryNextId'],globals:{uni:{reLaunch:x=>nav.push(x.url),showToast:x=>toasts.push(x.title)},setTimeout:()=>1,clearTimeout:()=>{}},mocks:{
  vue:{computed:f=>({get value(){return f()}}),ref:value=>({value}),nextTick:()=>Promise.resolve()},
  '@dcloudio/uni-app':{onShow:f=>callbacks.show=f,onHide:f=>callbacks.hide=f},
  '@/store/settings.js':{useSettings:()=>({load:()=>{},sensory:false,dnd:false})},'@/store/today.js':{useToday:()=>today},
  '@/store/user.js':{useUser:()=>({current:()=> 'u'})},'@/utils/focusFlow.js':{createFocusFlow:()=>flow},
  '@/utils/systemInfo.js':{getStatusBarHeight:()=>20},
  '@/utils/presentation.js':{idlePetUrl:()=>'',idleTimeoutSeconds:()=>300,loadManifest:async()=>null,petImageUrl:()=>''}
 }})
 return {ns,today,nav,callbacks,toasts,setResult:r=>{result=r},setPending:r=>{pending=r}}
}
test('退出失败不跳页、保留当前任务',async()=>{
 const t=await setup();await t.ns.onExit();assert.equal(t.nav.length,0);assert.equal(t.today.focus.session_id,'s')
})
test('退出成功回对话页，不跳备忘录也不自动存空回执',async()=>{
 const t=await setup();t.setResult({status:'finished'});await t.ns.onExit();assert.equal(t.nav[0],'/pages/chat/chat')
})
test('完成最后一项回对话页，继续下一项时留在专注页',async()=>{
 const t=await setup();t.setResult({status:'executing'});await t.ns.onDone();assert.equal(t.nav.length,0)
 t.setResult({status:'finished'});await t.ns.onDone();assert.equal(t.nav[0],'/pages/chat/chat')
})
test('下一项失败暴露重试入口，不展示假完成页',async()=>{
 const t=await setup();t.setResult({status:'next_failed',nextItemId:'b'});await t.ns.onDone()
 assert.equal(t.ns.retryNextId.value,'b');assert.equal(t.nav.length,0)
})
test('退出已成功但响应跨后台到达：等回前台再返回，不重启未完成任务',async()=>{
 const t=await setup();t.callbacks.hide();t.setResult({status:'finished'});await t.ns.onExit();assert.equal(t.nav.length,0)
 t.today.focus=null;t.setPending({id:'round'});await t.callbacks.show();assert.equal(t.nav[0],'/pages/chat/chat')
})
