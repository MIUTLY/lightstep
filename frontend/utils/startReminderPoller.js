/** 仅前台且有待提醒预约时检查；不重叠请求，不应用隐藏前的旧结果。 */
export function createStartReminderPoller(poll, {
	intervalMs = 15000,
	setIntervalFn = setInterval,
	clearIntervalFn = clearInterval,
	shouldPoll = () => true
} = {}) {
	let active = false
	let timer = null
	let inFlight = false
	let generation = 0

	function clearTimer() {
		if (timer !== null) clearIntervalFn(timer)
		timer = null
	}

	// 页面可见性与预约存在性分开：消费后可停表，同页改约仍可重新启动。
	function refresh() {
		if (!active || !shouldPoll()) {
			clearTimer()
			return
		}
		if (timer !== null) return
		timer = setIntervalFn(tick, intervalMs)
		void tick()
	}

	async function tick() {
		if (!active || !shouldPoll()) {
			refresh()
			return
		}
		if (inFlight) return
		const current = generation
		inFlight = true
		try {
			await poll(() => active && current === generation)
		} catch (_) {
			// 网络失败不刷错误气泡；下次可见检查再试。
		} finally {
			inFlight = false
			refresh()
			// hide/show期间没有并发发新请求；旧请求结束后立即补本次前台检查。
			if (active && current !== generation && shouldPoll()) void tick()
		}
	}

	return {
		start() {
			if (!active) {
				active = true
				generation += 1
			}
			refresh()
		},
		refresh,
		stop() {
			active = false
			generation += 1
			clearTimer()
		}
	}
}
