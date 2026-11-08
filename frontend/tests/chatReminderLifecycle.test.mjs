import test from 'node:test'
import assert from 'node:assert/strict'
import { loadFrontend, deferred } from './helpers/runtime.mjs'

async function setup() {
	const first = deferred(), next = deferred()
	const hooks = {}, counts = { start: 0, stop: 0, resume: 0 }
	const session = {
		open: () => first.promise, syncState: () => next.promise,
		startReminderChecks: () => counts.start++, stopReminderChecks: () => counts.stop++,
		fetchTodaySummary: async () => null
	}
	const mocks = {
		vue: { computed: fn => ({ get value() { return fn() } }), ref: value => ({ value }), nextTick: fn => fn(), watch() {} },
		'@dcloudio/uni-app': Object.fromEntries(['onShow', 'onHide', 'onUnload'].map(name => [name, fn => { hooks[name] = fn }])),
		'@/store/session.js': { useSession: () => session },
		'@/store/settings.js': { useSettings: () => ({ load() {}, dnd: false }) },
		'@/store/user.js': { useUser: () => ({ ensure() {} }) },
		'@/composables/useSoftRecall.js': { useSoftRecall: () => ({ resume: () => counts.resume++, stop() {}, poke() {}, reset() {} }) },
		'@/utils/systemInfo.js': { getStatusBarHeight: () => 0 },
		'@/utils/voice.js': { explainVoiceUnavailable() {}, isVoiceSupported: () => false, listenOnce() {} }
	}
	for (const name of ['CatBuddy', 'ChatBubble', 'QuickActions', 'SoftLine']) mocks[`@/components/${name}.vue`] = { default: {} }
	await loadFrontend('pages/chat/chat.vue', { mocks })
	return { first, next, hooks, counts }
}

test('首屏打开等待期间隐藏，完成后不得启动轮询或召回', async () => {
	const { first, hooks, counts } = await setup()
	const showing = hooks.onShow()
	hooks.onHide(); first.resolve(); await showing
	assert.equal(counts.start, 0)
	assert.equal(counts.resume, 0)
	assert.equal(counts.stop, 1)
})

test('快速隐藏再显示，只有最新onShow完成后启动检查', async () => {
	const { first, next, hooks, counts } = await setup()
	const oldShow = hooks.onShow()
	hooks.onHide()
	const newShow = hooks.onShow()
	next.resolve(); await newShow
	assert.equal(counts.start, 1)
	first.resolve(); await oldShow
	assert.equal(counts.start, 1)
	assert.equal(counts.resume, 1)
})

test('恢复查询未完成即卸载，不再恢复页面副作用', async () => {
	const { first, next, hooks, counts } = await setup()
	first.resolve(); await hooks.onShow()
	const showing = hooks.onShow()
	hooks.onUnload(); next.resolve(); await showing
	assert.equal(counts.start, 1)
	assert.equal(counts.stop, 1)
})

test('预约检查的API失败不弹toast，由前台下次检查重试', async () => {
	let options
	const { pollStartReminder } = await loadFrontend('api/index.js', {
		mocks: { './request.js': { post: async (...args) => { options = args; throw new Error('offline') }, get() {}, del() {} } }
	})
	await assert.rejects(pollStartReminder('user'), /offline/)
	assert.equal(options[0], '/api/reminders/poll')
	assert.equal(options[1].user_id, 'user')
	assert.equal(options[2]?.silent, true)
})
