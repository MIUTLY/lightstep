import test from 'node:test'
import assert from 'node:assert/strict'
import { loadFrontend } from './helpers/runtime.mjs'
import { fakeClock } from './helpers/anchorRuntime.mjs'

async function setup() {
	const clock = fakeClock()
	const { useFiveMinuteAnchor } = await loadFrontend('composables/useFiveMinuteAnchor.js', {
		mocks: { vue: { ref: value => ({ value }), onUnmounted() {} } }
	})
	const changes = []
	const anchor = useFiveMinuteAnchor({ now: clock.now, setTimeoutFn: clock.setTimeout, clearTimeoutFn: clock.clearTimeout, onChange: value => changes.push(value) })
	return { anchor, clock, changes }
}

test('确认开始后截止时间固定五分钟，重复start不延后', async () => {
	const { anchor, clock } = await setup()
	anchor.setForeground(true); anchor.start()
	const deadline = anchor.deadline.value
	assert.equal(deadline, clock.now() + 300000)
	clock.advance(100000); anchor.start()
	assert.equal(anchor.deadline.value, deadline)
	clock.advance(199999); assert.equal(anchor.due.value, false)
	clock.advance(1); assert.equal(anchor.due.value, true)
	assert.equal(clock.count, 0)
})

test('后台不依赖timeout运行，过期回前台才提示', async () => {
	const { anchor, clock } = await setup()
	anchor.setForeground(true); anchor.start(); clock.advance(60000)
	anchor.setForeground(false)
	assert.equal(clock.count, 0)
	clock.jump(300000)
	assert.equal(anchor.due.value, false)
	anchor.setForeground(true)
	assert.equal(anchor.due.value, true)
	assert.equal(clock.count, 0)
})

test('后台未到期时回来只等待剩余时间，不重算五分钟', async () => {
	const { anchor, clock } = await setup()
	anchor.setForeground(true); anchor.start(); clock.advance(60000)
	const deadline = anchor.deadline.value
	anchor.setForeground(false); clock.jump(120000); anchor.setForeground(true)
	assert.equal(anchor.deadline.value, deadline)
	clock.advance(119999); assert.equal(anchor.due.value, false)
	clock.advance(1); assert.equal(anchor.due.value, true)
})

test('到期只保持一份提示，继续才从当前时间续五分钟且不能连点续多轮', async () => {
	const { anchor, clock } = await setup()
	anchor.setForeground(true); anchor.start(); clock.advance(300000)
	const deadline = anchor.deadline.value
	clock.advance(900000)
	assert.equal(anchor.deadline.value, deadline)
	assert.equal(anchor.due.value, true)
	assert.equal(anchor.again(), true)
	const next = clock.now() + 300000
	assert.equal(anchor.deadline.value, next)
	clock.advance(20000); anchor.again()
	assert.equal(anchor.deadline.value, next)
	clock.advance(280000); assert.equal(anchor.due.value, true)
})

test('停止后清理截止时间与提示，已排队的旧timeout不能复活它', async () => {
	const { anchor, clock } = await setup()
	anchor.setForeground(true); anchor.start()
	const oldCallback = clock.callbacks[0]
	anchor.stop(); oldCallback(); clock.jump(600000); anchor.setForeground(true)
	assert.equal(anchor.deadline.value, null)
	assert.equal(anchor.due.value, false)
	assert.equal(clock.count, 0)
})

test('前台timeout延迟执行时按实际时间到期，重复恢复不重复建timer', async () => {
	const { anchor, clock } = await setup()
	anchor.setForeground(true); anchor.start()
	clock.jump(600000); anchor.setForeground(true); anchor.setForeground(true)
	assert.equal(anchor.due.value, true)
	assert.equal(clock.count, 0)
})
