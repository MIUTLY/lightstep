import test from 'node:test'
import assert from 'node:assert/strict'
import { loadFrontend, deferred, flush, fakeIntervals } from './helpers/runtime.mjs'

function ready(due = '2026-11-07T10:05:00+00:00', title = '写论文') {
	return { reply: '', state: 'ready', task: {
		title, current_step: '打开文档', step_id: 'task:s0', steps_done: 0,
		state: 'ready', start_due_at: due
	}, due_reminders: [], buttons: ['现在开始', '5分钟后', '10分钟后'] }
}

async function setup(overrides = {}) {
	const clock = fakeIntervals()
	const calls = []
	const user = { id: 'user' }
	const api = {
		openSession: async () => ready(), sessionState: async () => ready(),
		pollStartReminder: async () => ready(), chooseTime: async () => ready(),
		exitTask: async () => ({ state: 'idle', task: null, due_reminders: [] }),
		chat: async () => ready(), ...overrides
	}
	for (const [name, fn] of Object.entries(api)) api[name] = (...args) => {
		calls.push({ name, args }); return fn(...args)
	}
	const { useSession } = await loadFrontend('store/session.js', {
		mocks: { vue: { reactive: x => x }, './user.js': { useUser: () => ({ current: () => user.id }) }, '@/api/index.js': api },
		globals: { setInterval: clock.setInterval, clearInterval: clock.clearInterval }
	})
	const session = useSession()
	return { session, clock, calls, user, polls: () => calls.filter(c => c.name === 'pollStartReminder').length }
}

test('消费提醒只展示一次，保持ready和步骤，随后停止检查；改约重新启动', async () => {
	const due = { ...ready(null), due_reminders: ['之前约好开始'], reply: '' }
	const { session, clock, polls } = await setup({ pollStartReminder: async () => due })
	await session.open()
	session.startReminderChecks(); await flush()
	assert.equal(session.state, 'ready')
	assert.equal(session.task.steps_done, 0)
	assert.equal(session.task.current_step, '打开文档')
	assert.equal(session.messages.length, 2)
	assert.equal(session.reminders[0], '之前约好开始')
	assert.equal(session.navIntent, null)
	assert.equal(clock.count, 0)
	await clock.tick(); assert.equal(polls(), 1)
	await session.dispatchLabel('10分钟后'); await flush()
	assert.equal(polls(), 2)
	assert.equal(clock.count, 0)
	session.stopReminderChecks()
})

for (const label of ['现在开始', '今天不做', '10分钟后']) {
	test(`操作“${label}”后返回的旧轮询不覆盖任务或显示旧提醒`, async () => {
		const request = deferred()
		const next = label === '现在开始'
			? { ...ready(null), state: 'committing', task: { ...ready(null).task, state: 'committing' } }
			: label === '今天不做' ? { state: 'idle', task: null } : ready('2026-11-07T10:10:00+00:00')
		const { session, clock } = await setup({ pollStartReminder: () => request.promise, chooseTime: async () => next })
		await session.open(); session.startReminderChecks()
		await session.dispatchLabel(label)
		const before = JSON.stringify([session.task, session.state, session.messages, session.reminders])
		request.resolve({ ...ready(null, '旧任务'), due_reminders: ['旧提醒'] }); await flush()
		assert.equal(JSON.stringify([session.task, session.state, session.messages, session.reminders]), before)
		if (label !== '10分钟后') assert.equal(clock.count, 0)
		session.stopReminderChecks()
	})
}

test('退出或换任务后旧轮询不恢复原任务', async () => {
	for (const action of ['exit', 'replace']) {
		const request = deferred()
		const { session } = await setup({ pollStartReminder: () => request.promise, chat: async () => ready(null, '背单词') })
		await session.open(); session.startReminderChecks()
		if (action === 'exit') await session.exitTask()
		else await session.sendChat('换成背单词')
		const before = JSON.stringify([session.task, session.messages, session.state])
		request.resolve({ ...ready(), due_reminders: ['旧提醒'] }); await flush()
		assert.equal(JSON.stringify([session.task, session.messages, session.state]), before)
		session.stopReminderChecks()
	}
})

test('用户操作尚未完成时旧轮询不能显示提醒，失败后保留任务', async () => {
	const poll = deferred(), action = deferred()
	const { session } = await setup({ pollStartReminder: () => poll.promise, chooseTime: () => action.promise })
	await session.open(); session.startReminderChecks()
	const choosing = session.dispatchLabel('现在开始')
	poll.resolve({ ...ready(null), due_reminders: ['旧提醒'] }); await flush()
	assert.equal(session.reminders.length, 0)
	assert.equal(session.messages.length, 1)
	action.reject(new Error('离线')); await choosing
	assert.equal(session.state, 'ready')
	assert.ok(session.task.start_due_at)
	session.stopReminderChecks()
})

test('隐藏后旧轮询不能追加消息或改状态', async () => {
	const request = deferred()
	const { session, clock } = await setup({ pollStartReminder: () => request.promise })
	await session.open(); session.startReminderChecks(); session.stopReminderChecks()
	request.resolve({ ...ready(null), due_reminders: ['到点'] }); await flush()
	assert.equal(session.messages.length, 1)
	assert.equal(session.reminders.length, 0)
	assert.ok(session.task.start_due_at)
	assert.equal(clock.count, 0)
})

test('页面恢复状态的慢响应不覆盖之后的开始操作', async () => {
	const request = deferred()
	const committing = { ...ready(null), state: 'committing', task: { ...ready(null).task, state: 'committing' } }
	const { session } = await setup({ sessionState: () => request.promise, chooseTime: async () => committing })
	await session.open()
	const syncing = session.syncState()
	await session.dispatchLabel('现在开始')
	request.resolve(ready())
	await syncing
	assert.equal(session.state, 'committing')
	assert.equal(session.task.start_due_at, null)
})

test('多个恢复请求乱序返回时，以最后发起的有效查询为准', async () => {
	const first = deferred(), second = deferred()
	let n = 0
	const { session } = await setup({ sessionState: () => (++n === 1 ? first.promise : second.promise) })
	await session.open()
	const a = session.syncState(), b = session.syncState()
	second.resolve(ready(null, '新任务')); await b
	first.resolve(ready(null, '旧任务')); await a
	assert.equal(session.task.title, '新任务')
})

test('5/10分钟按钮使用对应枚举，轮询失败不追加系统气泡', async () => {
	const { session, clock, calls, polls } = await setup({ pollStartReminder: async () => { throw new Error('offline') } })
	await session.open()
	await session.dispatchLabel('5分钟后'); await session.dispatchLabel('10分钟后')
	assert.equal(calls.find(c => c.name === 'chooseTime').args[1], 'in_5_minutes')
	assert.equal(calls.filter(c => c.name === 'chooseTime')[1].args[1], 'in_10_minutes')
	const count = session.messages.length
	session.startReminderChecks(); await flush(); await clock.tick()
	assert.equal(session.messages.length, count)
	assert.equal(polls(), 2)
	session.stopReminderChecks()
})

test('无预约时不检查，在可见页面创建预约即开始检查', async () => {
	const { session, clock, polls } = await setup({ openSession: async () => ready(null) })
	await session.open(); session.startReminderChecks()
	assert.equal(clock.count, 0)
	await session.dispatchLabel('5分钟后'); await flush()
	assert.equal(polls(), 1)
	assert.equal(clock.count, 1)
	session.stopReminderChecks()
})


test('切换演示身份后不应用原身份的在途预约响应', async () => {
    const request = deferred()
    const { session, user } = await setup({ pollStartReminder: () => request.promise })
    await session.open(); session.startReminderChecks()
    user.id = 'other-user'
    request.resolve({ ...ready(null), due_reminders: ['原用户提醒'] }); await flush()
    assert.equal(session.reminders.length, 0)
    assert.equal(session.messages.length, 1)
    session.stopReminderChecks()
})
