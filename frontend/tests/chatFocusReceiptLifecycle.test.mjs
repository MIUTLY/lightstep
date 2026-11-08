import test from 'node:test'
import assert from 'node:assert/strict'
import { loadFrontend, deferred } from './helpers/runtime.mjs'
async function setup() {
 const callbacks={};const request=deferred();let restored=0,acked=0
 const today={events:[{id:'r',kind:'receipt'}],hasFocus:()=>false,load:()=>request.promise,ack:async()=>acked++}
 const ns=await loadFrontend('pages/chat/chat.vue',{expose:['pendingReceiptRound'],globals:{uni:{showToast:()=>{}}},mocks:{
  vue:{computed:f=>({get value(){return f()}}),nextTick:f=>Promise.resolve().then(f),ref:value=>({value}),watch:()=>{}},
  '@dcloudio/uni-app':{onShow:f=>callbacks.show=f,onHide:f=>callbacks.hide=f},
  '@/components/CatBuddy.vue':{default:{}},'@/components/ChatBubble.vue':{default:{}},'@/components/SoftLine.vue':{default:{}},'@/components/SideDrawer.vue':{default:{}},'@/components/FocusReceiptDialog.vue':{default:{}},
  '@/store/session.js':{useSession:()=>({open:async()=>{},syncState:async()=>{},messages:[]})},'@/store/today.js':{useToday:()=>today},
  '@/store/settings.js':{useSettings:()=>({load:()=>{}})},'@/store/user.js':{useUser:()=>({ensure:()=>{},current:()=> 'u'})},
  '@/utils/focusFlow.js':{createFocusFlow:()=>({recover:()=>restored++,pending:()=>({id:'round'})})},
  '@/utils/systemInfo.js':{getStatusBarHeight:()=>20},'@/utils/voice.js':{explainVoiceUnavailable:()=>'',isVoiceSupported:()=>false,listenOnce:()=>{}},
  '@/composables/useSoftRecall.js':{useSoftRecall:()=>({text:{value:''},poke:()=>{},resume:()=>{},stop:()=>{},reset:()=>{}})}
 }})
 return {ns,callbacks,request,getRestored:()=>restored,getAcked:()=>acked}
}
test('返回对话页先保存本轮回执事实再ack，自动打开弹窗',async()=>{
 const t=await setup();const pending=t.callbacks.show();t.request.resolve({items:[],focus:null});await pending
 assert.equal(t.getRestored(),1);assert.equal(t.getAcked(),1);assert.equal(t.ns.pendingReceiptRound.value.id,'round')
})
test('恢复请求失败不ack或假弹出回执',async()=>{
 const t=await setup();const pending=t.callbacks.show();t.request.resolve(null);await pending
 assert.equal(t.getRestored(),0);assert.equal(t.getAcked(),0);assert.equal(t.ns.pendingReceiptRound.value,null)
})
test('恢复期间进入后台，不在隐藏页显示弹窗',async()=>{
 const t=await setup();const pending=t.callbacks.show();t.callbacks.hide();t.request.resolve({items:[],focus:null});await pending
 assert.equal(t.getRestored(),0);assert.equal(t.ns.pendingReceiptRound.value,null)
})
