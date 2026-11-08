import test from 'node:test'
import assert from 'node:assert/strict'
import { loadFrontend } from './helpers/runtime.mjs'

test('窗口宽度优先现代接口，旧接口或异常环境能继续挂载', async () => {
 const cases = [
  [{ getWindowInfo: () => ({ windowWidth: 414 }), getSystemInfoSync: () => { throw Error('obsolete') } }, 414],
  [{ getWindowInfo: () => { throw Error('unavailable') }, getSystemInfoSync: () => ({ windowWidth: 320 }) }, 320],
  [{ getSystemInfoSync: () => ({ windowWidth: 390 }) }, 390],
  [{ getWindowInfo: () => ({ windowWidth: -1 }), getSystemInfoSync: () => ({ windowWidth: NaN }) }, 375],
  [{ getWindowInfo: () => { throw Error('denied') }, getSystemInfoSync: () => { throw Error('denied') } }, 375],
  [{}, 375]
 ]
 for (const [uni, expected] of cases) {
  const module = await loadFrontend('utils/systemInfo.js', { globals: { uni } })
  assert.equal(module.getWindowWidth(), expected)
 }
})

async function mount(round) {
 const painted = []
 const ns = await loadFrontend('components/FocusReceiptDialog.vue', {
  expose: ['line', 'displayWidth', 'rendering'],
  globals: {
   uni: { getSystemInfoSync: () => { throw Error('system info unavailable') }, createCanvasContext: () => ({}) },
   defineProps: () => ({ round, flow: { patch: () => {} } }),
   defineEmits: () => () => {}, setTimeout, clearTimeout
  },
  mocks: {
   vue: { ref: value => ({ value }), computed: fn => ({ get value() { return fn() } }),
    getCurrentInstance: () => ({ proxy: {} }), nextTick: () => Promise.resolve(),
    watch: (source, callback, options) => { if (options?.immediate) callback(source()) } },
   '@/utils/presentation.js': { receiptArt: () => null, downloadAsset: async () => '' },
   '@/utils/receipt.js': { RECEIPT_W: 600, RECEIPT_H: 900,
    drawReceipt: (ctx, options, done) => { painted.push(options); done() }, drawArtReceipt: () => {},
    exportCanvasTempPath: async () => '/unused' }
  }
 })
 await ns.rendering
 return { ns, painted }
}

test('回执按需首次挂载立即恢复原草稿并绘图，系统信息失败不阻止显示', async () => {
 const round = { id: 'saved-draft', draft: '明天接着写', receipts: [{ id: 'receipt', occurred_date: '2026-11-08' }] }
 const { ns, painted } = await mount(round)
 assert.equal(ns.line.value, round.draft)
 assert.equal(ns.displayWidth, 330)
 assert.equal(painted.length, 1)
 assert.equal(painted[0].line, round.draft)
 assert.equal(painted[0].date, '2026.11.08')
})

test('空回执挂载不下载、不绘图、不读写私人记录', async () => {
 const { ns, painted } = await mount(null)
 assert.equal(ns.line.value, '')
 assert.equal(painted.length, 0)
})
