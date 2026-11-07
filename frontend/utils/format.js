/** 展示层的小工具（只做格式化，不含业务） */

/** 后端 state 枚举 → 中文（聊天里的状态小胶囊用） */
const STATE_LABEL = {
	idle: '空闲',
	ready: '待开始',
	committing: '轻轻承诺',
	executing: '进行中',
	done: '完成'
}

export function stateLabel(state) {
	return STATE_LABEL[state] || state || ''
}

/** 后端 granularity 枚举 → 单字 */
const GRANULARITY_LABEL = {
	fine: '细',
	normal: '中',
	coarse: '粗'
}

export function granularityLabel(granularity) {
	return GRANULARITY_LABEL[granularity] || granularity || ''
}

/**
 * 小步的姿势随今日步数变化（策划书 9.2：1 步瘫着 / 3 步坐起 / 5 步以上伸懒腰）。
 * 返回 'sleep' | 'awake' | 'sit' | 'stretch'，由 CatBuddy 组件消费。
 */
export function catPoseOfSteps(steps) {
	const n = Number(steps) || 0
	if (n <= 0) return 'sleep'
	if (n <= 2) return 'awake'
	if (n <= 4) return 'sit'
	return 'stretch'
}

function pad2(n) {
	return n < 10 ? '0' + n : '' + n
}

/** '2026-11-07' → '11月7日' */
export function formatDateCN(dateStr) {
	if (!dateStr) return ''
	const parts = String(dateStr).split('-')
	if (parts.length !== 3) return dateStr
	return Number(parts[1]) + '月' + Number(parts[2]) + '日'
}

/** '2026-11-07T14:32:10' → '11-07 14:32' */
export function formatDateTime(isoStr) {
	if (!isoStr) return ''
	const m = String(isoStr).match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/)
	if (!m) return String(isoStr)
	return m[2] + '-' + m[3] + ' ' + m[4] + ':' + m[5]
}

/** 今天（客户端本地时间），用于回执右下角；注意后端也用自己的服务器时间 */
export function todayCN() {
	const d = new Date()
	return d.getFullYear() + '.' + pad2(d.getMonth() + 1) + '.' + pad2(d.getDate())
}

/**
 * 按钮文案展示替换：后端 buttons 里用的是「完成这一步」，
 * 单步页按策划书 F2 的说法显示成「这步做完了」；映射只影响展示，点击仍上报原标签。
 */
const LABEL_DISPLAY = {
	完成这一步: '这步做完了'
}

export function displayLabel(raw) {
	return LABEL_DISPLAY[raw] || raw
}

/** 把毫秒换算成给后端 duration_ms 用的安全整数（最小 1s，最多 30min） */
export function safeDuration(ms) {
	const n = Math.round(Number(ms) || 0)
	return Math.min(Math.max(n, 1000), 30 * 60 * 1000)
}
