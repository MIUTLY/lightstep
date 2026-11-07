/** 只在页面可见时检查；慢请求不重叠，隐藏后旧响应不得更新页面。 */
export function createStartReminderPoller(poll, {
	intervalMs = 15000,
	setIntervalFn = setInterval,
	clearIntervalFn = clearInterval
} = {}) {
	let active = false
	let timer = null
	let inFlight = false
	let generation = 0

	async function tick() {
		if (!active || inFlight) return
		const current = generation
		inFlight = true
		try {
			await poll(() => active && current === generation)
		} catch (_) {
			// 网络失败不刷错误气泡；下次可见检查再试。
		} finally {
			inFlight = false
		}
	}

	return {
		start() {
			if (active) return
			active = true
			generation += 1
			timer = setIntervalFn(tick, intervalMs)
			void tick()
		},
		stop() {
			active = false
			generation += 1
			if (timer !== null) clearIntervalFn(timer)
			timer = null
		}
	}
}
