<template>
 <view v-if="round" class="receipt-mask" @touchmove.stop.prevent>
  <view class="receipt-dialog">
   <view class="receipt-head"><text>本轮专注回执</text><text @tap="close">稍后再看</text></view>
   <scroll-view scroll-y class="receipt-body">
    <text class="receipt-facts">{{ outcomeText }}</text>
    <view :style="previewBoxStyle"><canvas canvas-id="roundReceipt" id="roundReceipt" class="receipt-preview" :style="canvasStyle" /></view>
    <textarea class="receipt-writing" :value="line" :maxlength="-1" :disabled="saving" placeholder="写在回执下半部分的话（可不填）" @input="onInput" />
    <text v-if="error" class="receipt-error">{{ error }}</text>
    <view class="receipt-save" @tap="save"><text>{{ saving ? '正在保存…' : '保存至手帐' }}</text></view>
   </scroll-view>
  </view>
 </view>
</template>
<script setup>
import { computed, getCurrentInstance, nextTick, ref, watch } from 'vue'
import { drawArtReceipt, drawReceipt, exportCanvasTempPath, RECEIPT_W, RECEIPT_H } from '@/utils/receipt.js'
import { receiptArt, downloadAsset } from '@/utils/presentation.js'
import { addEntry, persistImage, discardImage } from '@/utils/localJournal.js'
const props = defineProps({ round: { type: Object, default: null }, flow: { type: Object, required: true } })
const emit = defineEmits(['closed'])
const instance = getCurrentInstance()
const line = ref(''), error = ref(''), saving = ref(false)
const displayWidth = Math.min(RECEIPT_W, (uni.getSystemInfoSync().windowWidth || 375) * 0.88)
const previewBoxStyle = 'position:relative;margin:auto;overflow:hidden;width:' + displayWidth + 'px;height:' + displayWidth * RECEIPT_H / RECEIPT_W + 'px;'
const canvasStyle = 'position:absolute;left:0;top:0;transform:scale(' + displayWidth / RECEIPT_W + ');transform-origin:top left;width:' + RECEIPT_W + 'px;height:' + RECEIPT_H + 'px;'
const last = computed(() => props.round?.receipts?.slice(-1)[0] || null)
const outcomeText = computed(() => (props.round?.outcome || last.value?.outcome) === 'interrupted' ? '这次先到这里，剩下的进度已经留好。' : '本轮约定的行动做完了，歇一会儿吧。')
let generation = 0
let rendering = Promise.resolve()
async function render(text, round, token) {
 await nextTick()
 if (token !== generation || !round) return
 const receipt = round.receipts.slice(-1)[0]
 const art = receiptArt(receipt?.presentation)
 const path = art ? await downloadAsset(art.url) : ''
 if (token !== generation) return
 if (art && !path) throw new Error('票根图片没加载成功，内容已保留，请重试保存')
 await new Promise((resolve, reject) => {
  const timer = setTimeout(() => reject(new Error('绘制未完成，请重试')), 10000)
  const done = () => { clearTimeout(timer); resolve() }
  try {
   const ctx = uni.createCanvasContext('roundReceipt', instance.proxy)
   const date = String(receipt?.occurred_date || receipt?.date || '').replace(/-/g, '.')
   if (art) drawArtReceipt(ctx, { imagePath: path, imageWidth: art.width, imageHeight: art.height, composition: art.composition, dateText: date, line: text }, done)
   else drawReceipt(ctx, { steps: 0, date, line: text }, done)
  } catch (e) { clearTimeout(timer); reject(e) }
 })
}
function redraw() {
 const token = ++generation, text = line.value, round = props.round
 rendering = rendering.catch(() => {}).then(() => render(text, round, token))
 rendering.catch(e => { if (token === generation) error.value = e.message })
 return rendering
}
watch(() => props.round?.id, () => { line.value = props.round?.draft || ''; error.value = ''; redraw() })
function onInput(e) {
 if (saving.value) return
 line.value = e.detail.value; error.value = ''
 try { props.flow.patch(props.round.id, { draft: line.value }) } catch (e) { error.value = '暂时不能保存草稿，请保留当前页面' }
 redraw()
}
async function save() {
 if (saving.value || !props.round) return
 saving.value = true; error.value = ''
 const round = props.round, text = line.value
 let savedPath = '', indexed = false
 try {
  await redraw()
  const temp = await exportCanvasTempPath('roundReceipt', instance.proxy)
  const path = await persistImage(temp)
  if (!path) throw new Error('图片未保存成功，请保留文字后重试')
  savedPath = path
  const receipts = round.receipts, receipt = receipts.slice(-1)[0]
  const record = addEntry({ id: round.id, note: text, imagePath: path,
   occurred_date: receipt.occurred_date || receipt.date,
   titles: [...new Set(receipts.map(e => e.title))], receipt_event_ids: receipts.map(e => e.id) })
  if (!record) throw new Error('手帐索引未保存成功，请重试')
  indexed = true
  if (record.imagePath !== path) await discardImage(path)
  props.flow.patch(round.id, { dismissed: true, saved: true, draft: text })
  uni.showToast({ title: '已保存至手帐', icon: 'none' }); emit('closed')
 } catch (e) {
  if (savedPath && !indexed) await discardImage(savedPath)
  error.value = e.message || '这次没存成功，请重试'
 }
 finally { saving.value = false }
}
function close() {
 if (saving.value) return
 try { props.flow.patch(props.round.id, { deferred: true, draft: line.value }); emit('closed') }
 catch (e) { error.value = '暂时无法保存草稿，请保留当前页面' }
}
</script>
<style scoped>
.receipt-mask{position:fixed;inset:0;z-index:1200;background:rgba(40,33,25,.4);display:flex;align-items:center;justify-content:center}
.receipt-dialog{background:#fbf8f2;width:94vw;max-height:94vh;border-radius:24rpx;overflow:hidden}
.receipt-head{display:flex;justify-content:space-between;padding:24rpx;color:#54483c}
.receipt-body{height:80vh}.receipt-facts{display:block;padding:16rpx 24rpx;color:#6b6055}
.receipt-preview{margin:0 auto;transform-origin:top left}/* 输入框做成「有横线的纸」：字号比正文小两档（30 → 24rpx），
   行高 40rpx，横线画在每行**基线上**（相对行顶 27rpx；基线 ≈ (40-24)/2 + 0.8×24 ≈ 27），
   这样光标和字都压在线上，而不是浮在两条线中间。 */
.receipt-writing{margin:24rpx;box-sizing:border-box;width:calc(100% - 48rpx);min-height:120rpx;padding:8rpx 10rpx;font-size:24rpx;line-height:40rpx;color:#3d3d3d;background:repeating-linear-gradient(to bottom,transparent 0,transparent 27rpx,#d9cfc1 27rpx,#d9cfc1 28rpx,transparent 28rpx,transparent 40rpx)}
.receipt-save{margin:24rpx;padding:24rpx;background:#dd9a39;color:white;text-align:center;border-radius:16rpx}.receipt-error{display:block;margin:20rpx;color:#8b4939}
</style>
