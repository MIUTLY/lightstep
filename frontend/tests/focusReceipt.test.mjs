import test from 'node:test'
import assert from 'node:assert/strict'
import { loadFrontend } from './helpers/runtime.mjs'
async function setup() {
 const data=new Map(),toasts=[],painted=[],closed=[],fields=[]
 let persistFails=false,indexFails=false,downloadFails=false
 const round={id:'round1',receipts:[{id:'receipt1',title:'数学',date:'2026-11-08',occurred_date:'2026-11-08',outcome:'interrupted',presentation:{}}]}
 const uni={getSystemInfoSync:()=>({windowWidth:375}),getStorageSync:k=>data.get(k),setStorageSync:(k,v)=>{if(indexFails)throw Error('full');data.set(k,v)},
  getFileSystemManager:()=>({saveFile:({success,fail})=>persistFails?fail():success({savedFilePath:'wxfile://persisted'})}),
  createCanvasContext:()=>({}),showToast:v=>toasts.push(v.title)}
 const props={round,flow:{patch:(id,value)=>fields.push(value)}}
 const ns=await loadFrontend('components/FocusReceiptDialog.vue',{expose:['save','onInput','line','error','close'],globals:{uni,setTimeout,clearTimeout,defineProps:()=>props,defineEmits:()=>name=>closed.push(name)},mocks:{
  vue:{computed:f=>({get value(){return f()}}),ref:value=>({value}),getCurrentInstance:()=>({proxy:{}}),nextTick:()=>Promise.resolve(),watch:()=>{}},
  '@/utils/presentation.js':{receiptArt:()=>({url:'/art',composition:{}}),downloadAsset:async()=>downloadFails?'':'/local-art'},
  '@/utils/receipt.js':{RECEIPT_W:600,RECEIPT_H:900,drawArtReceipt:(ctx,opts,done)=>{painted.push(opts.line);done()},drawReceipt:()=>{},exportCanvasTempPath:async()=>'/tmp/export'}
 }})
 return {ns,data,toasts,painted,closed,fields,setPersistFail:v=>{persistFails=v},setIndexFail:v=>{indexFails=v},setDownloadFail:v=>{downloadFails=v}}
}
test('先填写后保存：预览和导出用当前文字，保存完整图片和本地索引',async()=>{
 const t=await setup();t.ns.onInput({detail:{value:'下次接着做'}});await t.ns.save()
 const pages=JSON.parse(t.data.get('lightstep_local_journal'));assert.equal(pages[0].note,'下次接着做');assert.equal(pages[0].imagePath,'wxfile://persisted')
 assert.equal(t.painted.at(-1),'下次接着做');assert.ok(t.toasts.includes('已保存至手帐'));assert.equal(t.closed.length,1)
})
test('图片保存失败保留文字，不创建假成功记录',async()=>{
 const t=await setup();t.ns.line.value='原始文字';t.setPersistFail(true);await t.ns.save()
 assert.equal(t.ns.line.value,'原始文字');assert.equal(t.data.has('lightstep_local_journal'),false);assert.equal(t.toasts.length,0);assert.match(t.ns.error.value,/图片未保存/)
})
test('索引保存失败不提示成功；重试和重复保存只产生一页',async()=>{
 const t=await setup();t.ns.line.value='草稿';t.setIndexFail(true);await t.ns.save();assert.equal(t.toasts.length,0)
 t.setIndexFail(false);await t.ns.save();await t.ns.save();assert.equal(JSON.parse(t.data.get('lightstep_local_journal')).length,1)
})
test('票根下载失败不保存旧图或空图片',async()=>{
 const t=await setup();t.setDownloadFail(true);await t.ns.save();assert.equal(t.data.has('lightstep_local_journal'),false);assert.equal(t.toasts.length,0)
})
test('同一天不同轮次追加，旧页不覆盖',async()=>{
 const store=new Map();const uni={getStorageSync:k=>store.get(k),setStorageSync:(k,v)=>store.set(k,v)}
 const ns=await loadFrontend('utils/localJournal.js',{globals:{uni}})
 ns.addEntry({id:'one',occurred_date:'2026-11-08',note:'第一轮'});ns.addEntry({id:'two',occurred_date:'2026-11-08',note:'第二轮'})
 assert.equal(ns.listEntries().length,2);assert.equal(ns.listEntries()[1].note,'第一轮')
})
test('已有超过500页不静默删旧记录，损坏索引不覆盖原数据',async()=>{
 const data=new Map(),key='lightstep_local_journal';data.set(key,JSON.stringify(Array.from({length:501},(_,i)=>({id:'old'+i}))))
 const ns=await loadFrontend('utils/localJournal.js',{globals:{uni:{getStorageSync:k=>data.get(k),setStorageSync:(k,v)=>data.set(k,v)}}})
 ns.addEntry({id:'new'});assert.equal(ns.listEntries().length,502)
 data.set(key,'broken');assert.equal(ns.addEntry({id:'another'}),null);assert.equal(data.get(key),'broken')
})

test('未保存时收起只保留草稿，不把回执标为永久已处理',async()=>{
 const t=await setup();t.ns.line.value='草稿仍在';t.ns.close()
 assert.equal(t.fields[0].draft,'草稿仍在');assert.equal(t.fields[0].deferred,true);assert.equal(t.fields[0].dismissed,undefined)
})
