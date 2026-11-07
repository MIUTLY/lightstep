/**
 * 语音输入（策划书 F1：「支持文字输入 + 语音输入，连打字都懒的时候直接说」）
 *
 * 后端现状：**没有** ASR / 语音转写接口（只有 /api/chat 收文本）。
 * 所以这里做两件事，绝不假装后端能听懂语音：
 *
 *  1. 如果小程序里已申请并配置了微信「同声传译」插件（WechatSI），
 *     就用插件在**端内**把话转成文字，再把文字交给 /api/chat —— 这条路是真的能用的，
 *     只是需要在微信公众平台添加插件、manifest 里声明，属于「运营配置」，不是代码问题。
 *  2. 没配插件时，弹一句说明，并把输入框聚焦让用户打字。
 *
 * 怎么开启（两步，见 README「语音输入」）：
 *   a. 微信公众平台 → 设置 → 第三方设置 → 插件管理 → 添加「同声传译」(wx069ba97219f66d99)
 *   b. manifest.json 的 mp-weixin 节点里加：
 *      "plugins": { "WechatSI": { "version": "0.3.5", "provider": "wx069ba97219f66d99" } }
 */

let cachedPlugin = null
let cached = false

function getPlugin() {
	if (cached) return cachedPlugin
	cached = true
	try {
		// 只在 mp-weixin 且已声明插件时才存在；其余平台会直接抛错
		if (typeof requirePlugin === 'function') {
			cachedPlugin = requirePlugin('WechatSI')
		}
	} catch (e) {
		cachedPlugin = null
	}
	return cachedPlugin
}

export function isVoiceSupported() {
	const plugin = getPlugin()
	return !!(plugin && plugin.getRecordRecognitionManager)
}

/**
 * 录一句话并返回识别到的文字。
 * @returns {Promise<string>} 识别结果（可能为空串）
 */
export function listenOnce() {
	const plugin = getPlugin()
	if (!plugin || !plugin.getRecordRecognitionManager) {
		return Promise.reject(new Error('VOICE_UNAVAILABLE'))
	}

	const manager = plugin.getRecordRecognitionManager()

	return new Promise((resolve, reject) => {
		let settled = false

		manager.onStop = (res) => {
			if (settled) return
			settled = true
			resolve((res && res.result) || '')
		}
		manager.onError = (err) => {
			if (settled) return
			settled = true
			reject(new Error((err && err.msg) || '语音识别失败'))
		}

		uni.showToast({ title: '说吧，我在听', icon: 'none', duration: 1500 })
		manager.start({ duration: 30000, lang: 'zh_CN' })
	})
}

/** 语音不可用时的统一提示（不假装成功） */
export function explainVoiceUnavailable() {
	uni.showModal({
		title: '语音输入还没接上',
		content:
			'后端目前只提供文本对话接口（/api/chat），没有语音转写。\n先在输入框打字就行；想开语音的话，按 README 里的两步配置微信同声传译插件。',
		showCancel: false,
		confirmText: '好'
	})
}
