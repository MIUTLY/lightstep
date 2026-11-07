/** 系统信息小工具（custom 导航栏页面要自己让出状态栏高度） */

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
