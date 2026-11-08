/** Run against real uni-app mp-weixin build output, without a global `uni`.
 * Usage: node --test frontend/tests/compiledFocusSmoke.cjs (LIGHTSTEP_MP_BUILD required)
 * Only the WeChat platform/vendor boundary is substituted; this is not device UI acceptance.
 */
const test = require('node:test')
const assert = require('node:assert/strict')
const vm = require('node:vm')
const fs = require('node:fs')
const path = require('node:path')
const build = process.env.LIGHTSTEP_MP_BUILD
if (!build) throw new Error('Set LIGHTSTEP_MP_BUILD to the actual uni-app mp-weixin output directory')
function harness(extra = {}) {
 const memory = new Map(), props = [], callbacks = {}, registered = {}
 const vendor = {
  index: { getStorageSync: k => memory.get(k), setStorageSync: (k,v) => memory.set(k,v) },
  ref: value => ({value}), computed: fn => ({get value() { return fn() }}),
  watch: (source, fn, opts) => { if (opts?.immediate) fn(source()) },
  getCurrentInstance: () => ({proxy:{}}), nextTickMP: fn => Promise.resolve().then(fn),
  onShow: fn => {callbacks.show=fn}, onHide: fn => {callbacks.hide=fn},
  unref: value => value && Object.hasOwn(value, 'value') ? value.value : value,
  _export_sfc: component => component, e: (...objects) => Object.assign({}, ...objects),
  p: value => {props.push(value); return value}, o: fn => fn, s: v => v, t: v => String(v),
  sr: () => '', n: v => v, f: (list, fn) => list.map(fn)
 }
 const mocks = {'common/vendor.js':vendor, ...extra}
 const context = vm.createContext({console,setTimeout,clearTimeout,wx:{
  createComponent: c => {registered.component=c}, createPage: p => {registered.page=p}
 }})
 const cache = new Map()
 function load(name) {
  name = name.replaceAll('\\','/')
  if (Object.hasOwn(mocks,name)) return mocks[name]
  if (cache.has(name)) return cache.get(name)
  const exports = {};cache.set(name,exports)
  const source = fs.readFileSync(path.join(build,name),'utf8')
  const execute = vm.runInContext('(function(require,exports){\n'+source+'\n})',context,{filename:name})
  execute(spec => load(path.posix.normalize(path.posix.join(path.posix.dirname(name),spec))),exports)
  return exports
 }
 return {load,vendor,memory,props,callbacks,registered}
}
test('compiled focus flow uses platform storage without a global uni', () => {
 const h=harness(), flow=h.load('utils/focusFlow.js').createFocusFlow({today:{},userId:()=> 'u'})
 const id=flow.begin();flow.collect([{id:'receipt',kind:'receipt',title:'洗衣服'}]);flow.finish()
 assert.equal(flow.pending().id,id)
 assert.equal(flow.pending().receipts[0].id,'receipt')
 assert.equal(h.memory.size,1)
})
test('compiled window helper uses modern API and survives both APIs throwing', () => {
 const h=harness(), info=h.load('utils/systemInfo.js')
 h.vendor.index.getWindowInfo=()=>({windowWidth:412})
 assert.equal(info.getWindowWidth(),412)
 h.vendor.index.getWindowInfo=()=>{throw Error('unavailable')}
 h.vendor.index.getSystemInfoSync=()=>{throw Error('unavailable')}
 assert.equal(info.getWindowWidth(),375)
})
test('compiled receipt first mount restores draft and starts preview even when system APIs fail', async () => {
 const drawn=[]
 const h=harness({
  'utils/receipt.js':{RECEIPT_W:600,RECEIPT_H:900,drawReceipt:(ctx,options,done)=>{drawn.push(options);done()}},
  'utils/presentation.js':{receiptArt:()=>null}, 'utils/localJournal.js':{}
 })
 h.vendor.index.getWindowInfo=()=>{throw Error('unavailable')}
 h.vendor.index.getSystemInfoSync=()=>{throw Error('unavailable')}
 h.vendor.index.createCanvasContext=()=>({})
 h.load('components/FocusReceiptDialog.js')
 const round={id:'round',draft:'继续加油',receipts:[{id:'r',occurred_date:'2026-11-08'}]}
 const render=h.registered.component.setup({round,flow:{patch:()=>{}}},{emit:()=>{}})
 assert.doesNotThrow(()=>render({},{ }))
 await new Promise(resolve=>setImmediate(resolve))
 assert.equal(drawn.length,1)
 assert.equal(drawn[0].line,'继续加油')
 assert.equal(drawn[0].date,'2026.11.08')
})
test('compiled chat setup and first render work without global uni and do not mount an empty receipt', () => {
 const today={items:[],firstClarification:()=>null,hasFocus:()=>false}
 const h=harness({
  'common/assets.js':{_imports_0:'paper.jpg'},
  'store/session.js':{useSession:()=>({hasTalked:false,task:null,messages:[]})},
  'store/settings.js':{useSettings:()=>({})},'store/today.js':{useToday:()=>today},
  'store/user.js':{useUser:()=>({current:()=> 'u'})},
  'composables/useSoftRecall.js':{useSoftRecall:()=>({text:{value:''},poke:()=>{},resume:()=>{},stop:()=>{},reset:()=>{}})},
  'utils/voice.js':{}
 })
 h.load('pages/chat/chat.js')
 const render=h.registered.page.setup({})
 assert.doesNotThrow(()=>render({},{}))
 assert.equal(h.props.some(p=>Object.hasOwn(p,'round')),false)
 assert.equal(typeof h.callbacks.show,'function')
})
