import { ref, onUnmounted } from 'vue'

/**
 * 隐形番茄钟：5 分钟轻承诺的到点提醒（策划书 8-第三步）
 *
 * 关键点是「不显示倒计时」——界面上没有任何数字在跑，
 * 只有到点的那一刻，屏幕下方轻轻出现两个很小的按钮：
 *   就到这吧 / 再来 5 分钟
 * 它不挽留、不说「再坚持一下」，选择权完全交给用户。
 *
 * 同时这也是唯一会打断用户的东西，所以：
 *  - 页面 onHide 时停表（切后台不烧时间）
 *  - 用户一旦点「到这儿」就彻底停掉
 */
export function useFiveMinuteAnchor(options = {}) {
	const durationMs = options.durationMs || 5 * 60 * 1000
	const due = ref(false)
	let timer = null

	function clear() {
		if (timer) {
			clearTimeout(timer)
			timer = null
		}
	}

	/** 开始一个 5 分钟锚点 */
	function start() {
		clear()
		due.value = false
		timer = setTimeout(() => {
			timer = null
			due.value = true
		}, durationMs)
	}

	/** 「再来 5 分钟」 */
	function again() {
		start()
	}

	/** 停表（切后台 / 退出任务） */
	function stop() {
		clear()
	}

	/** 收起提示但不停表（用户已经看到了） */
	function dismiss() {
		due.value = false
	}

	onUnmounted(stop)

	return { due, start, again, stop, dismiss }
}
