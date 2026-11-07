import test from 'node:test'
import assert from 'node:assert/strict'
import { deferred } from './helpers/runtime.mjs'
import { sessionRuntime, reply } from './helpers/anchorRuntime.mjs'

test('只有确认成功进入executing才起算，选时间/拒绝不启动', async () => {
	const { session, clock } = await sessionRuntime()
	session.setFiveMinuteForeground(true)
	await session.open(); await session.dispatchLabel('现在开始')
	assert.equal(session.anchorDeadline, null)
	await session.dispatchLabel('再想想')
	assert.equal(session.anchorDeadline, null)
	await session.dispatchLabel('现在开始'); await session.dispatchLabel('行')
	assert.equal(session.anchorDeadline, clock.now() + 300000)
})

test('确认请求失败不启动轻承诺', async () => {
	const { session } = await sessionRuntime({ commit: async () => { throw new Error('offline') } })
	await session.open(); await session.dispatchLabel('现在开始'); await session.dispatchLabel('行')
	assert.equal(session.state, 'committing')
	assert.equal(session.anchorDeadline, null)
})

test('换步、拆小、记便签不重置，过期不自动调用完成或退出接口', async () => {
	const { session, clock, calls, begin } = await sessionRuntime()
	session.setFiveMinuteForeground(true); await begin()
	const deadline = session.anchorDeadline
	clock.advance(50000); await session.completeStep()
	clock.advance(50000); await session.resize('smaller')
	clock.advance(50000); await session.sendNote('取快递')
	assert.equal(session.anchorDeadline, deadline)
	const before = JSON.stringify([session.task, calls])
	clock.advance(150000)
	assert.equal(session.anchorDue, true)
	assert.equal(session.state, 'executing')
	assert.equal(JSON.stringify([session.task, calls]), before)
})

test('后台累计且隐藏提示，回前台过期后询问；继续只续时不推进步骤', async () => {
	const { session, clock, calls, begin } = await sessionRuntime()
	session.setFiveMinuteForeground(true); await begin()
	clock.advance(60000); session.setFiveMinuteForeground(false); clock.jump(300000)
	assert.equal(session.anchorDue, false)
	session.setFiveMinuteForeground(true)
	assert.equal(session.anchorDue, true)
	const before = JSON.stringify([session.task, calls])
	session.continueFiveMinutes()
	assert.equal(session.anchorDue, false)
	assert.equal(session.anchorDeadline, clock.now() + 300000)
	assert.equal(JSON.stringify([session.task, calls]), before)
})

test('结束失败保留到期提示，重试成功才清理任务和轻承诺', async () => {
	let failures = 1
	const { session, clock, begin } = await sessionRuntime({ exitTask: async () => { if (failures--) throw new Error('offline'); return reply('idle') } })
	session.setFiveMinuteForeground(true); await begin(); clock.advance(300000)
	await session.exitTask()
	assert.equal(session.anchorDue, true)
	assert.equal(session.state, 'executing')
	await session.exitTask()
	assert.equal(session.anchorDue, false)
	assert.equal(session.anchorDeadline, null)
	assert.equal(session.state, 'idle')
})

test('正在结束时不能用继续按钮重启锚点，结束成功后不再提示', async () => {
	const response = deferred()
	const { session, clock, begin } = await sessionRuntime({ exitTask: () => response.promise })
	session.setFiveMinuteForeground(true); await begin(); clock.advance(300000)
	const deadline = session.anchorDeadline
	const exiting = session.exitTask()
	session.continueFiveMinutes()
	assert.equal(session.anchorDeadline, deadline)
	response.resolve(reply('idle')); await exiting
	assert.equal(session.anchorDeadline, null)
})

test('任务完成、明确换任务以及同步发现任务消失会清理锚点', async () => {
	for (const action of ['done', 'switch', 'sync']) {
		const { session, clock, begin } = await sessionRuntime({ stepComplete: async () => reply('done'), sessionState: async () => reply('idle') })
		session.setFiveMinuteForeground(true); await begin()
		if (action === 'done') await session.completeStep()
		if (action === 'switch') await session.sendChat('换成背单词')
		if (action === 'sync') await session.syncState()
		assert.equal(session.anchorDeadline, null)
		clock.advance(600000); assert.equal(session.anchorDue, false)
	}
})

test('进程内页面重建与状态刷新不重启，旧执行态恢复不伪造新承诺', async () => {
	const { session, clock, begin } = await sessionRuntime()
	await begin(); const deadline = session.anchorDeadline
	clock.jump(100000); await session.syncState()
	assert.equal(session.anchorDeadline, deadline)
	const cold = await sessionRuntime({ openSession: async () => reply() })
	await cold.session.open()
	assert.equal(cold.session.anchorDeadline, null)
})

test('演示身份更换后停止原身份的轻承诺', async () => {
	const { session, clock, user, begin } = await sessionRuntime()
	session.setFiveMinuteForeground(true); await begin()
	user.id = 'other-user'; clock.advance(300000)
	assert.equal(session.anchorDue, false)
	assert.equal(session.anchorDeadline, null)
})


test('已到期后手动完成步骤仍保留提示，不自动续一轮', async () => {
    const { session, clock, begin } = await sessionRuntime()
    session.setFiveMinuteForeground(true); await begin(); clock.advance(300000)
    const deadline = session.anchorDeadline
    await session.completeStep()
    assert.equal(session.anchorDue, true)
    assert.equal(session.anchorDeadline, deadline)
    await session.exitTask()
})

test('预约的五分钟不会启动执行轻承诺，只有后续确认成功才起算', async () => {
    const { session, clock } = await sessionRuntime({ chooseTime: async (_, when) => when === 'now'
        ? reply('committing') : { ...reply('ready'), task: { ...reply('ready').task, start_due_at: '2026-11-07T12:05:00Z' } } })
    session.setFiveMinuteForeground(true); await session.open()
    await session.dispatchLabel('5分钟后'); clock.advance(360000)
    assert.equal(session.state, 'ready')
    assert.equal(session.anchorDue, false)
    assert.equal(session.anchorDeadline, null)
    await session.dispatchLabel('现在开始'); await session.dispatchLabel('行')
    assert.equal(session.anchorDeadline, clock.now() + 300000)
    await session.exitTask()
})
