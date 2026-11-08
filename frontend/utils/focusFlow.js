/** Durable local outbox for one uninterrupted focus round spanning multiple memo items.
 * Backend receipt facts are saved before acknowledgement; personal drafts never go to the API.
 */
import { newRequestId } from './requestId.js'
// 注意：默认参数里**不能**直接引用那个全局对象（写出来就是裸标识符）。
// uni-app 的 mp-weixin 编译器只会把 `uni.xxx` 这种成员访问改写成 common_vendor.index，
// 裸标识符会原样留下，运行时报 ReferenceError: uni is not defined
//（2026-11-08 13:34 实测：chat 页直接白屏 + Component is missing template）。
// 所以这里延迟到调用时才取成员方法。
function uniStorage() {
 return {
  getStorageSync: (key) => uni.getStorageSync(key),
  setStorageSync: (key, value) => uni.setStorageSync(key, value)
 }
}
export function createFocusFlow({ today, userId, storage }) {
 const box = storage || uniStorage()
 const key = () => 'lightstep_focus_rounds_' + userId()
 function read() {
  const raw = box.getStorageSync(key())
  const value = raw ? (typeof raw === 'string' ? JSON.parse(raw) : raw) : { rounds: [], current: null }
  if (!value || !Array.isArray(value.rounds)) throw new Error('回执记录暂时无法读取，请保留当前页面')
  return value
 }
 function write(value) { box.setStorageSync(key(), JSON.stringify(value)) }
 function begin() {
  const box = read()
  if (!box.current) {
   const round = { id: newRequestId(), receipts: [], ready: false, dismissed: false, draft: '' }
   box.rounds.push(round); box.current = round.id; write(box)
  }
  return box.current
 }
 function collect(events) {
  const known = new Set(read().rounds.flatMap(r => r.receipts.map(e => e.id)))
  const receipts = (events || []).filter(e => e && e.kind === 'receipt' && !known.has(e.id))
  if (!receipts.length) return
  begin(); const box = read(); const round = box.rounds.find(r => r.id === box.current)
  const seen = new Set(box.rounds.flatMap(r => r.receipts.map(e => e.id)))
  for (const e of receipts) if (!seen.has(e.id)) { round.receipts.push(e); seen.add(e.id) }
  write(box)
 }
 function finish(outcome = 'completed') {
  const box = read(); const round = box.rounds.find(r => r.id === box.current)
  if (round) { round.ready = round.receipts.length > 0; round.outcome = outcome; box.current = null; write(box) }
 }
 function pending() {
  const rounds = read().rounds.filter(r => r.ready && !r.dismissed).reverse()
  return rounds.find(r => !r.deferred) || rounds[0] || null
 }
 function patch(id, fields) {
  const box = read(); const r = box.rounds.find(r => r.id === id)
  if (r) { Object.assign(r, fields); write(box) }
 }
 let running = false
 async function complete() {
  if (running || today.busy || !today.focus) return { status: 'busy' }
  running = true
  try {
   begin(); const date = today.date
   const view = await today.complete()
   if (!view || view.operation?.status !== 'succeeded') return { status: 'failed' }
   collect(view.events)
   if (today.focus) return { status: 'executing' }
   const next = view.date === date ? view.suggested_item_id : null
   if (next) {
    const selected = await today.select(next)
    if (selected?.operation?.status === 'succeeded' && selected.focus) return { status: 'executing' }
    if (!selected || selected.operation?.status === 'failed') return { status: 'next_failed', nextItemId: next }
    finish('interrupted'); return { status: 'clarification' }
   }
   finish(); return { status: 'finished' }
  } finally { running = false }
 }
 async function retryNext(id) {
  if (running || today.busy) return { status: 'busy' }
  running = true
  try {
   if (today.focus) return { status: 'executing' }
   collect(today.events)
   const view = await today.select(id)
   if (view?.operation?.status === 'succeeded' && view.focus) return { status: 'executing' }
   if (!view || view.operation?.status === 'failed') return { status: 'next_failed', nextItemId: id }
   finish('interrupted'); return { status: 'clarification' }
  } finally { running = false }
 }
 async function end() {
  if (running || today.busy) return { status: 'busy' }
  running = true
  try {
   begin()
   if (today.focus) {
    const view = await today.end()
    if (!view || view.operation?.status !== 'succeeded' || view.focus) return { status: 'failed' }
    collect(view.events)
   }
   collect(today.events)
   finish('interrupted'); return { status: 'finished' }
  } finally { running = false }
 }
 function recover(events, hasFocus) {
  collect(events)
  if (!hasFocus) finish((events || []).filter(e => e.kind === 'receipt').slice(-1)[0]?.outcome === 'interrupted' ? 'interrupted' : 'completed')
 }
 return { begin, collect, finish, pending, patch, complete, retryNext, end, recover }
}
