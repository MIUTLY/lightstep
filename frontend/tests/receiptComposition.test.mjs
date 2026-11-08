import test from 'node:test'
import assert from 'node:assert/strict'
import { loadFrontend } from './helpers/runtime.mjs'
async function painter() {
 const ns=await loadFrontend('utils/receipt.js')
 const calls=[],ctx=new Proxy({}, {get:(_,name)=> (...args)=>{calls.push({name,args});if(name==='draw')args[1]()}})
 const composition={coordinate_space:[1696,2528],text_box:{x:280,y:1940,width:1120,height:250},
  date_cover:{x:1040,y:2310,width:470,height:75},date_patch_source:{x:400,y:2310,width:470,height:75},date_text_box:{x:1040,y:2310,width:470,height:75}}
 return {ns,ctx,calls,opts:{imagePath:'wxfile://art',imageWidth:1280,imageHeight:1908,composition,dateText:'2026.11.08',line:'下次继续'}}
}
test('日期补丁源坐标按实际图片尺寸计算，不能当作600x900画布坐标',async()=>{
 const {ns,ctx,calls,opts}=await painter();ns.drawArtReceipt(ctx,opts,()=>{})
 const source=calls.filter(c=>c.name==='drawImage')[1].args
 assert.ok(Math.abs(source[1]-400*1280/1696)<.01);assert.ok(Math.abs(source[2]-2310*1908/2528)<.01)
 assert.ok(Math.abs(source[5]-1040*600/1696)<.01)
})
test('长文字超出时拒绝保存，不悄悄截断',async()=>{
 const {ns,ctx,opts}=await painter();assert.throws(()=>ns.drawArtReceipt(ctx,{...opts,line:'字'.repeat(3000)},()=>{}),/超出/)
})
test('底图绘制失败向调用方报错，不能导出空白成功票根',async()=>{
 const {ns,ctx,opts}=await painter();ctx.drawImage=()=>{throw Error('canvas failed')}
 // Use an ordinary context for this failure; the successful painter uses a recording Proxy.
 const failed=new Proxy({}, {get:(_,name)=>name==='drawImage'?()=>{throw Error('canvas failed')}:()=>{}})
 assert.throws(()=>ns.drawArtReceipt(failed,opts,()=>{}),/底图绘制失败/)
})

test('旧数据中性票根也保留完整文字，超过三行拒绝而非截断',async()=>{
 const {ns,ctx,calls}=await painter()
 const text='这是超过原来十八字限制的一段话，仍然应该全部保存在回执里。'
 ns.drawReceipt(ctx,{line:text,date:'2026.11.08'},()=>{})
 const rendered=calls.filter(c=>c.name==='fillText').map(c=>c.args[0]).join('')
 for (const ch of text) assert.ok(rendered.includes(ch))
 assert.throws(()=>ns.drawReceipt(ctx,{line:'字'.repeat(1000)},()=>{}),/超出/)
})

test('用户文字基线落在票根印好的横线上，字号比原来小两档',async()=>{
 const {ns,ctx,calls,opts}=await painter()
 ns.drawArtReceipt(ctx,opts,()=>{})
 const drawn=calls.filter(c=>c.name==='fillText'&&c.args[0]==='下次继续')[0]
 // text_box y=1940 h=250、行距 0.54*250=135 → 第一条线 2015，画布缩放 900/2528
 const lineY=(1940+250*0.3)*900/2528
 assert.ok(Math.abs(drawn.args[2]-(lineY-3))<.01,'基线应该落在第一条横线上（比线高高 3px，字形下缘才贴住线）')
 const fontSize=calls.filter(c=>c.name==='setFontSize').map(c=>c.args[0])
 const textSize=fontSize[fontSize.length-1]
 assert.ok(textSize<=34,'字号上限从 44 降到 34（小两档）')
 assert.ok(textSize>=12)
})
test('素材给了 text_baselines 时优先照它落笔',async()=>{
 const {ns,ctx,calls,opts}=await painter()
 const withLines={...opts,composition:{...opts.composition,text_baselines:[2015,2150,2285]}}
 ns.drawArtReceipt(ctx,withLines,()=>{})
 const drawn=calls.filter(c=>c.name==='fillText'&&c.args[0]==='下次继续')[0]
 assert.ok(Math.abs(drawn.args[2]-(2015*900/2528-3))<.01)
})
