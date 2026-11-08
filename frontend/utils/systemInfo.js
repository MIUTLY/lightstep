/** 系统信息小工具（custom 导航栏页面要自己让出状态栏高度） */

/** 回执预览只需要窗口宽度；平台接口异常不应阻止页面挂载。 */
export function getWindowWidth() {
	for (const method of ['getWindowInfo', 'getSystemInfoSync']) {
		try {
			if (typeof uni[method] !== 'function') continue
			const width = Number(uni[method]()?.windowWidth)
			if (Number.isFinite(width) && width > 0) return width
		} catch (e) {
			// 尝试兼容接口，两个都不可用时使用稳定的预览宽度。
		}
	}
	return 375
}

export function getStatusBarHeight() {
	try {
		const info =
			typeof uni.getWindowInfo === 'function' ? uni.getWindowInfo() : uni.getSystemInfoSync()
		return (info && info.statusBarHeight) || 0
	} catch (e) {
		return 0
	}
}

/** 底部安全区（全面屏 Home 指示条），单位 px */
export function getSafeAreaBottom() {
	try {
		const info =
			typeof uni.getWindowInfo === 'function' ? uni.getWindowInfo() : uni.getSystemInfoSync()
		const area = info && info.safeArea
		const height = info && info.screenHeight
		if (area && height) return Math.max(0, height - area.bottom)
		return 0
	} catch (e) {
		return 0
	}
}
