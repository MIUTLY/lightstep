import test from 'node:test'
import assert from 'node:assert/strict'
import { loadFrontend, deferred, flush, fakeIntervals } from './helpers/runtime.mjs'

async function setup(poll, shouldPoll = () => true) {
	const { createStartReminderPoller } = await loadFrontend('utils/startReminderPoller.js')
	const clock = fakeIntervals()
	const poller = createStartReminderPoller(poll, {
		shouldPoll, setIntervalFn: clock.setInterval, clearIntervalFn: clock.clearInterval
	})
	return { poller, clock }
}

test('前台立即检查，重复start不增加计时器，慢网不重叠', async () => {
	const request = deferred()
	let calls = 0
	const { poller, clock } = await setup(() => { calls++; return request.promise })
	poller.start(); poller.start()
	assert.equal(calls, 1)
	assert.equal(clock.count, 1)
	await clock.tick(); await clock.tick()
	assert.equal(calls, 1)
	request.resolve(); await flush()
	await clock.tick()
	assert.equal(calls, 2)
	poller.stop()
	assert.equal(clock.count, 0)
})

test('隐藏或卸载后清理计时器，使未完成请求的应用凭证失效', async () => {
	const request = deferred()
	let applied = 0
	const { poller, clock } = await setup(async isCurrent => {
		await request.promise
		if (isCurrent()) applied++
	})
	poller.start(); poller.stop(); poller.stop()
	request.resolve(); await flush(); await clock.tick()
	assert.equal(applied, 0)
	assert.equal(clock.count, 0)
})

test('隐藏再显示时等旧慢请求结束，立即检查新一代且不应用旧结果', async () => {
	const first = deferred()
	let calls = 0, applied = 0
	const { poller, clock } = await setup(async isCurrent => {
		calls++
		if (calls === 1) await first.promise
		if (isCurrent()) applied++
	})
	poller.start(); poller.stop(); poller.start()
	assert.equal(calls, 1)
	first.resolve(); await flush()
	assert.equal(calls, 2)
	assert.equal(applied, 1)
	assert.equal(clock.count, 1)
	poller.stop()
})

test('没有待提醒预约时不建计时器，当前页新预约可重新启动', async () => {
	let pending = false, calls = 0
	const { poller, clock } = await setup(async () => { calls++ }, () => pending)
	poller.start()
	assert.equal(clock.count, 0)
	assert.equal(calls, 0)
	pending = true; poller.refresh(); await flush()
	assert.equal(clock.count, 1)
	assert.equal(calls, 1)
	poller.stop()
})

test('提醒消费后关闭计时器，改约后可再次启动', async () => {
	let pending = true, calls = 0
	const { poller, clock } = await setup(async () => { calls++; pending = false }, () => pending)
	poller.start(); await flush()
	assert.equal(clock.count, 0)
	await clock.tick()
	assert.equal(calls, 1)
	pending = true; poller.refresh(); await flush()
	assert.equal(calls, 2)
	assert.equal(clock.count, 0)
	poller.stop()
})

test('网络失败不产生未处理异常，下一次前台检查可以重试', async () => {
	let calls = 0
	const { poller, clock } = await setup(async () => {
		if (++calls === 1) throw new Error('offline')
	})
	poller.start(); await flush(); await clock.tick()
	assert.equal(calls, 2)
	poller.stop()
})
