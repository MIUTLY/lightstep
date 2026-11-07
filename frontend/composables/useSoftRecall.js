import { ref, onUnmounted } from 'vue'

/**
 * 温和漂移召回（策划书 F3）
 *
 * 规则（照 PRD 逐条实现）：
 *  - 仅前台运行时计时：页面 onHide 时 stop()，onShow 时重新 arm()
 *  - 有任何触摸操作就重置计时（页面根节点 @touchstart → poke()）
 *  - 5 分钟完全没碰屏幕才触发
 *  - 无声音、无弹窗、无红色警告，只是轻轻浮起一行字
 *  - 最多提醒 2 次，之后安静等待，绝不催第三次
 *  - 「勿扰」开关开着时完全不提醒
 *
 * @param {Object} options
 * @param {number} [options.idleMs=300000] 多久没碰屏幕算走神（默认 5 分钟）
 * @param {number} [options.maxTimes=2]    最多提醒几次
 * @param {Function} [options.enabled]     返回 false 时不提醒（接「勿扰」开关）
 * @param {number} [options.showMs=8000]   那句话浮在屏幕上的时长
 */
export function useSoftRecall(options = {}) {
	const idleMs = options.idleMs || 5 * 60 * 1000
	const maxTimes = typeof options.maxTimes === 'number' ? options.maxTimes : 2
	const showMs = options.showMs || 8000
	const enabled = typeof options.enabled === 'function' ? options.enabled : () => true
	const line = options.line || '我在这儿，需要了叫我'

	const text = ref('')
	let timer = null
	let hideTimer = null
	let times = 0

	function clearTimers() {
		if (timer) {
			clearTimeout(timer)
			timer = null
		}
		if (hideTimer) {
			clearTimeout(hideTimer)
			hideTimer = null
		}
	}

	function arm() {
		if (timer) {
			clearTimeout(timer)
			timer = null
		}
		if (!enabled()) return
		if (times >= maxTimes) return
		timer = setTimeout(() => {
			timer = null
			times += 1
			text.value = line
			if (hideTimer) clearTimeout(hideTimer)
			hideTimer = setTimeout(() => {
				text.value = ''
				hideTimer = null
			}, showMs)
			// 第 1 次之后还留着第 2 次的机会，第 2 次之后就不再计时了
			arm()
		}, idleMs)
	}

	/** 任何触摸 / 输入都算「人在」 */
	function poke() {
		text.value = ''
		arm()
	}

	/** 页面隐藏 / 关闭：停表，不算走神 */
	function stop() {
		clearTimers()
		text.value = ''
	}

	/** 重新开始一轮（回到页面时用，不重置已提醒次数） */
	function resume() {
		arm()
	}

	/** 完全重置（换任务、回到对话页时用） */
	function reset() {
		clearTimers()
		text.value = ''
		times = 0
		arm()
	}

	onUnmounted(stop)

	return {
		text,
		arm,
		stop,
		poke,
		resume,
		reset,
		timesShown: () => times
	}
}
