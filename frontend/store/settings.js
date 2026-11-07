import { defineStore } from './defineStore.js'
import { STORAGE_KEYS } from '@/config/index.js'

/**
 * 本地偏好 store（全部存本地，不上云）
 *
 * sensory      感官友好模式：纯黑白 + 关闭所有动效（策划书 F5）
 * dnd          勿扰：关掉温和召回（F3 角落里那个极小的开关）
 * showAllSteps 显示全部步骤（策划书说「设置里可以开」，
 *              但后端 TaskView 只返回 current_step、没有完整步骤数组，
 *              所以这一项目前是「已禁用 + 待接入」，见 docs/字段映射与联调说明.md）
 */
const DEFAULTS = {
	sensory: false,
	dnd: false,
	showAllSteps: false
}

export const useSettings = defineStore('settings', {
	state: () => ({
		loaded: false,
		sensory: DEFAULTS.sensory,
		dnd: DEFAULTS.dnd,
		showAllSteps: DEFAULTS.showAllSteps
	}),
	actions: (state) => ({
		load() {
			if (state.loaded) return
			let saved = null
			try {
				saved = uni.getStorageSync(STORAGE_KEYS.settings) || null
			} catch (e) {
				saved = null
			}
			if (saved && typeof saved === 'object') {
				state.sensory = !!saved.sensory
				state.dnd = !!saved.dnd
				state.showAllSteps = !!saved.showAllSteps
			}
			state.loaded = true
		},

		persist() {
			try {
				uni.setStorageSync(STORAGE_KEYS.settings, {
					sensory: state.sensory,
					dnd: state.dnd,
					showAllSteps: state.showAllSteps
				})
			} catch (e) {
				/* ignore */
			}
		},

		toggleSensory() {
			state.sensory = !state.sensory
			this.persist()
		},

		toggleDnd() {
			state.dnd = !state.dnd
			this.persist()
		},

		/** 换肤用的根节点 class */
		themeClass() {
			return state.sensory ? 'theme-sensory' : ''
		}
	})
})
