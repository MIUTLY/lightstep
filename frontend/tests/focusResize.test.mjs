import test from 'node:test'
import assert from 'node:assert/strict'
import { loadFrontend, deferred } from './helpers/runtime.mjs'

// Exercise the actual page handlers and today store together; only platform/API boundaries are replaced.
async function setup() {
 const calls = [], toasts = [], disk = new Map()
 const initialFocus = { session_id: 'session-a', title: '写作业',
  step: { step_id: 'forest:medium:remaining', current_step: '尝试解这道题' },
  progress: { completed_actions: ['读题'], remaining_actions: ['查知识点', '尝试一种思路'] },
  presentation: { completed_steps: 1, step_number: 2 } }
 const view = (revision, step, operation = { status: 'succeeded' }) => ({
  revision, date: '2026-11-08', items: [{ id: 'a' }, { id: 'b' }],
  focus: { ...initialFocus, step }, operation
 })
 let respond = async payload => view(2, {
  step_id: 'forest:' + payload.direction + ':remaining',
  current_step: payload.direction === 'smaller' ? '查一下相关知识点' : '读题后尝试一种思路'
 })
 const ns = await loadFrontend('pages/focusmode/focusmode.vue', {
  expose: ['onLighter', 'onHeavier', 'today', 'currentStep', 'transitionBusy', 'exiting'],
  globals: {
   uni: { getStorageSync: key => disk.get(key), setStorageSync: (key, value) => disk.set(key, value),
    showToast: value => toasts.push(value.title) },
   setTimeout: () => 1, clearTimeout: () => {}
  },
  mocks: {
   vue: { reactive: value => value, ref: value => ({ value }),
    computed: fn => ({ get value() { return fn() } }), nextTick: () => Promise.resolve() },
   '@dcloudio/uni-app': { onShow: () => {}, onHide: () => {} },
   '@/store/settings.js': { useSettings: () => ({ load: () => {}, sensory: false }) },
   '@/utils/systemInfo.js': { getStatusBarHeight: () => 20 },
   '@/utils/presentation.js': { idlePetUrl: () => '', idleTimeoutSeconds: () => 300,
    loadManifest: async () => null, petImageUrl: () => '' },
   '@/api/index.js': { today: async () => view(1, initialFocus.step),
    todayCommand: async payload => { calls.push(payload); return respond(payload) } }
  }
 })
 await ns.today.load()
 return { ns, calls, toasts, initialFocus, view, setRespond: fn => { respond = fn } }
}

test('轻重按钮发出对应resize请求，页面使用返回节点且不改变完成进度', async () => {
 const t = await setup()
 await t.ns.onLighter()
 assert.equal(t.calls.length, 1)
 assert.equal(t.calls[0].action, 'resize')
 assert.equal(t.calls[0].direction, 'smaller')
 assert.equal(t.calls[0].session_id, 'session-a')
 assert.equal(t.calls[0].step_id, 'forest:medium:remaining')
 assert.ok(t.calls[0].request_id)
 assert.ok(t.calls[0].user_id)
 assert.equal(t.ns.currentStep.value, '查一下相关知识点')
 await t.ns.onHeavier()
 assert.equal(t.calls.length, 2)
 assert.equal(t.calls[1].direction, 'bigger')
 assert.equal(t.calls[1].step_id, 'forest:smaller:remaining')
 assert.equal(t.ns.currentStep.value, '读题后尝试一种思路')
 assert.deepEqual(t.ns.today.focus.progress, t.initialFocus.progress)
 assert.deepEqual(t.ns.today.focus.presentation, t.initialFocus.presentation)
 assert.equal(t.ns.today.items.length, 2)
})

test('等待响应、切换任务或退出期间不发出额外轻重请求', async () => {
 const t = await setup(), request = deferred()
 t.ns.transitionBusy.value = true
 await t.ns.onLighter(); await t.ns.onHeavier()
 assert.equal(t.calls.length, 0)
 t.ns.transitionBusy.value = false
 t.ns.exiting.value = true
 await t.ns.onLighter(); await t.ns.onHeavier()
 assert.equal(t.calls.length, 0)
 t.ns.exiting.value = false
 t.setRespond(() => request.promise)
 const first = t.ns.onLighter()
 await t.ns.onHeavier()
 assert.equal(t.calls.length, 1)
 request.resolve(t.view(2, { step_id: 'light', current_step: '查知识点' }))
 await first
 assert.equal(t.ns.today.busy, false)
})

test('轻重切换断网明确提示，保留当前节点与进度并允许重试', async () => {
 const t = await setup()
 t.setRespond(async () => { throw new Error('网络连接失败，请重试') })
 await t.ns.onLighter()
 assert.equal(t.toasts.at(-1), '网络连接失败，请重试')
 assert.equal(t.ns.currentStep.value, t.initialFocus.step.current_step)
 assert.deepEqual(t.ns.today.focus.progress, t.initialFocus.progress)
 t.setRespond(async () => t.view(2, { step_id: 'light', current_step: '查知识点' }))
 await t.ns.onLighter()
 assert.equal(t.calls.length, 2)
 assert.equal(t.ns.currentStep.value, '查知识点')
})

test('轻重切换业务失败显示原因，不假装已经切换', async () => {
 const t = await setup()
 t.setRespond(async () => t.view(2, t.initialFocus.step,
  { status: 'failed', error: { message: '步骤已变化，请刷新' } }))
 await t.ns.onHeavier()
 assert.equal(t.toasts.at(-1), '步骤已变化，请刷新')
 assert.equal(t.ns.currentStep.value, t.initialFocus.step.current_step)
})

test('最轻或最重保持服务端返回节点，无专注时不发送请求', async () => {
 const t = await setup()
 t.setRespond(async () => t.view(2, t.initialFocus.step))
 await t.ns.onLighter()
 assert.equal(t.calls.length, 1)
 assert.equal(t.ns.currentStep.value, t.initialFocus.step.current_step)
 assert.equal(t.toasts.length, 0)
 t.ns.today.focus = null
 await t.ns.onHeavier()
 assert.equal(t.calls.length, 1)
 assert.equal(t.toasts.at(-1), '这一步还没开始，先回清单点一下')
})

test('调整动作意外抛出异常时显示提示且保留当前任务', async () => {
 const t = await setup()
 t.ns.today.resize = async () => { throw new Error('调整暂时不可用，请重试') }
 await t.ns.onLighter()
 assert.equal(t.toasts.at(-1), '调整暂时不可用，请重试')
 assert.equal(t.ns.currentStep.value, t.initialFocus.step.current_step)
 assert.deepEqual(t.ns.today.focus.progress, t.initialFocus.progress)
})
