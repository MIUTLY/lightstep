import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

// 非CLI工程没有package.json；直接导入该纯ES模块，不安装构建依赖。
const source = await readFile(new URL('../utils/stepIdentity.js', import.meta.url), 'utf8')
const { stepKey } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'))

test('相同文字的两个真实动作使用不同计时标识', () => {
	const a = { title: '阅读', current_step: '读一小段', step_id: 'p:s0' }
	const b = { ...a, step_id: 'p:s1' }
	assert.notEqual(stepKey(a), stepKey(b))
})

test('同一步刷新或恢复保持相同标识', () => {
	const task = { title: '阅读', current_step: '读一小段', step_id: 'p:s0' }
	assert.equal(stepKey(task), stepKey({ ...task }))
})

test('旧后端及空任务仍可兼容', () => {
	assert.equal(stepKey({ title: '阅读', current_step: '读一页' }), '阅读|读一页')
	assert.equal(stepKey(null), '')
})
