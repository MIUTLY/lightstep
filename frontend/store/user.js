import { defineStore } from './defineStore.js'
import { STORAGE_KEYS } from '@/config/index.js'

/**
 * 身份 store。
 *
 * 后端没有账号体系（策划书第 11 节「不做的功能」明确不做账号系统），
 * 身份就是一个客户端本地生成、长期保存的 user_id：
 *   - 生成规则与后端 static/app.js 一致：u_ + 随机串 + 时间戳36进制
 *   - 持久化在 uni storage，卸载小程序前不变
 *   - 摩擦地图 / 跨天交接 / 手帐都挂在这个 user_id 下，所以换 id 等于换一个人
 */
function randomId() {
	return 'u_' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36)
}

export const useUser = defineStore('user', {
	state: () => ({
		userId: '',
		restored: false
	}),
	actions: (state) => ({
		/** 冷启动调用：从缓存恢复，没有就新建一个 */
		ensure() {
			if (state.userId) return state.userId
			let saved = ''
			try {
				saved = uni.getStorageSync(STORAGE_KEYS.userId) || ''
			} catch (e) {
				saved = ''
			}
			if (!saved) {
				saved = randomId()
				try {
					uni.setStorageSync(STORAGE_KEYS.userId, saved)
				} catch (e) {
					/* 缓存写失败也不阻塞使用，只是换设备会丢记忆 */
				}
			}
			state.userId = saved
			state.restored = true
			return saved
		},

		/** 重置身份（设置页「换一个人」）：摩擦地图会重新开始积累 */
		reset() {
			const next = randomId()
			state.userId = next
			try {
				uni.setStorageSync(STORAGE_KEYS.userId, next)
			} catch (e) {
				/* ignore */
			}
			return next
		},

		/** 当前 user_id（保证已初始化） */
		current() {
			return state.userId || this.ensure()
		}
	})
})
