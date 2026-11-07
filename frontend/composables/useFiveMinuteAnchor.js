import { ref } from 'vue'

/**
 * 会话级五分钟轻承诺。后台按截止时间继续累计，不依赖后台timeout；
 * 回到前台再检查并显示选择。此实例由session持有，不随步骤或页面重建。
 */
export function useFiveMinuteAnchor(options = {}) {
	const durationMs = options.durationMs || 5 * 60 * 1000
	const now = options.now || Date.now
	const setTimeoutFn = options.setTimeoutFn || setTimeout
	const clearTimeoutFn = options.clearTimeoutFn || clearTimeout
	const onChange = options.onChange || (() => {})
	const due = ref(false)
	const deadline = ref(null)
	let foreground = false
	let timer = null
	let generation = 0

	function clear() {
		generation += 1
		if (timer !== null) clearTimeoutFn(timer)
		timer = null
	}

	function publish() {
		onChange({ due: due.value, deadline: deadline.value })
	}

	function check() {
		clear()
		due.value = foreground && deadline.value !== null && now() >= deadline.value
		if (foreground && deadline.value !== null && !due.value) {
			const version = generation
			timer = setTimeoutFn(() => {
				if (version !== generation) return
				timer = null
				check()
			}, Math.max(0, deadline.value - now()))
		}
		publish()
	}

	function begin() {
		deadline.value = now() + durationMs
		check()
		return true
	}

	return {
		due,
		deadline,
		start() {
			if (deadline.value !== null) return false
			return begin()
		},
		again() {
			if (!due.value) return false
			return begin()
		},
		stop() {
			clear()
			deadline.value = null
			due.value = false
			publish()
		},
		setForeground(value) {
			foreground = !!value
			check()
		},
		check
	}
}
