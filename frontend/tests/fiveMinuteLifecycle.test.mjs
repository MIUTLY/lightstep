import test from 'node:test'
import assert from 'node:assert/strict'
import { loadFrontend, deferred } from './helpers/runtime.mjs'
import { fakeClock, sessionRuntime } from './helpers/anchorRuntime.mjs'

const vue = { ref: value => ({ value }), onUnmounted() {}, computed: fn => ({ get value() { return fn() } }) }

test('App生命周期分别通知会话前台/后台；路由切换没有重置承诺', async () => {
	const hooks = {}, visibility = []
	await loadFrontend('App.vue', { mocks: {
		'@dcloudio/uni-app': Object.fromEntries(['onLaunch', 'onShow', 'onHide'].map(k => [k, fn => { hooks[k] = fn }])),
		'@/store/session.js': { useSession: () => ({ setFiveMinuteForeground: value => visibility.push(value) }) },
		'@/store/user.js': { useUser: () => ({ ensure() {} }) },
		'@/store/settings.js': { useSettings: () => ({ load() {} }) }
	} })
	hooks.onLaunch(); hooks.onShow(); hooks.onHide(); hooks.onShow()
	assert.deepEqual(visibility, [true, false, true])
})

test('轻承诺与无操作召回独立：触摸不续承诺，后台时间不触发无操作召回', async () => {
	const clock = fakeClock()
	const { useFiveMinuteAnchor } = await loadFrontend('composables/useFiveMinuteAnchor.js', { mocks: { vue } })
	const { useSoftRecall } = await loadFrontend('composables/useSoftRecall.js', { mocks: { vue }, globals: { setTimeout: clock.setTimeout, clearTimeout: clock.clearTimeout } })
	const anchor = useFiveMinuteAnchor({ now: clock.now, setTimeoutFn: clock.setTimeout, clearTimeoutFn: clock.clearTimeout })
	const recall = useSoftRecall()
	anchor.setForeground(true); anchor.start(); recall.resume()
	const deadline = anchor.deadline.value
	clock.advance(60000); recall.poke()
	assert.equal(anchor.deadline.value, deadline)
	anchor.setForeground(false); recall.stop(); clock.jump(300000)
	anchor.setForeground(true); recall.resume()
	assert.equal(anchor.due.value, true)
	assert.equal(recall.timesShown(), 0)
	assert.equal(recall.text.value, '')
	clock.advance(300000)
	assert.equal(recall.timesShown(), 1)
	assert.equal(anchor.deadline.value, deadline)
	anchor.stop(); recall.stop()
})

test('继续与结束按钮使用现有会话动作，不调用完成步骤；busy时不退出', async () => {
	const calls = []
	const session = { busy: false, continueFiveMinutes: () => calls.push('continue'), exitTask: async () => calls.push('exit') }
	const choice = await loadFrontend('components/FiveMinuteChoice.vue', { mocks: { '@/store/session.js': { useSession: () => session } }, expose: ['continueForFive', 'endNow'] })
	choice.continueForFive(); await choice.endNow()
	session.busy = true; await choice.endNow()
	assert.deepEqual(calls, ['continue', 'exit'])
})

test('focus收起/隐藏/卸载与换步保留同一个会话截止时间', async () => {
	const { session, clock, begin } = await sessionRuntime()
	session.setFiveMinuteForeground(true); await begin()
	const deadline = session.anchorDeadline
	const hooks = {}, watches = [], navigation = []
	const mocks = {
		vue: { ...vue, watch: (source, fn) => watches.push({ source, fn }) },
		'@dcloudio/uni-app': Object.fromEntries(['onShow', 'onHide', 'onUnload'].map(k => [k, fn => { hooks[k] = fn }])),
		'@/store/session.js': { useSession: () => session },
		'@/store/settings.js': { useSettings: () => ({ load() {}, dnd: false }) },
		'@/utils/systemInfo.js': { getStatusBarHeight: () => 0 },
		'@/composables/useSoftRecall.js': { useSoftRecall: () => ({ reset() {}, stop() {}, poke() {}, resume() {} }) }
	}
	for (const name of ['CatBuddy', 'SoftLine', 'FiveMinuteChoice']) mocks[`@/components/${name}.vue`] = { default: {} }
	const page = await loadFrontend('pages/focus/focus.vue', { mocks, expose: ['collapse'], globals: {
		setTimeout: clock.setTimeout, clearTimeout: clock.clearTimeout,
		getCurrentPages: () => [{}, {}], uni: { navigateBack: () => navigation.push('back') }
	} })
	await hooks.onShow()
	assert.equal(clock.count, 1)
	const change = watches.find(w => w.source() === 's0')
	await session.completeStep(); change.fn()
	page.collapse(); hooks.onHide(); await hooks.onShow(); hooks.onUnload()
	assert.equal(session.anchorDeadline, deadline)
	assert.equal(clock.count, 1)
	assert.deepEqual(navigation, ['back'])
	clock.advance(300000)
	assert.equal(session.anchorDue, true)
	await session.exitTask()
})

test('确认中途身份改变，旧响应不创建另一身份的承诺', async () => {
	const response = deferred()
	const { session, user } = await sessionRuntime({ commit: () => response.promise })
	await session.open(); await session.dispatchLabel('现在开始')
	const committing = session.dispatchLabel('行')
	user.id = 'other-user'
	response.resolve({ state: 'executing', task: { state: 'executing' } }); await committing
	assert.equal(session.anchorDeadline, null)
})
