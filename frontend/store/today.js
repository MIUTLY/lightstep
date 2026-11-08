/**
 * 新人主流程：今日备忘录 + 独立任务森林（/api/today*）
 *
 * 为什么单独一个 store：
 *   旧版 store/session.js 是「单任务」模型（task + 五态 + 预约提醒），
 *   而后端 2026-11-07 之后的主流程换成了「今日清单」：先 intake 出多条任务，
 *   用户选中某条 → 生成/复用一棵森林 → 专注 → 完成或中途结束 → 回执事件。
 *   两套状态形状完全不同，硬塞进 session 会让两边都难维护，所以并行存在：
 *     - session：旧的单任务（workflow=legacy 兼容）
 *     - today  ：新的今日备忘录（默认主流程）
 *
 * 后端契约（docs/today-memo.md）：
 *   GET  /api/today?user_id=&date=        读清单
 *   POST /api/today/command               写操作，公共字段 user_id + request_id
 *        action: intake | reorder | select | resize | complete | end | ack
 *   GET  /api/today/operation(s)          找回原命令和结果
 *   POST /api/focus/capture               专注页里新增任务
 *
 * 响应形状：
 *   { state:'memo'|'executing', revision, date, today_date, available_dates,
 *     items:[{id,title,completed,scope,question,...}], focus:{...}|null,
 *     suggested_item_id, reply, all_completed, today_all_completed,
 *     events:[...], navigation:{sidebar_locked,can_collapse_focus},
 *     operation:{request_id,status,error} }
 *
 * ⚠️ operation.status 可能是 succeeded / needs_clarification / failed，
 *    而 HTTP 仍然是 200 —— 所以**不能只看 HTTP 状态**判断成功。
 */
import { defineStore } from './defineStore.js'
import * as api from '@/api/index.js'
import { useUser } from './user.js'
import { newRequestId } from '@/utils/requestId.js'

/** 本地已处理过的事件 id（幂等：刷新/重试会重复下发同一事件，不能重复建条目） */
const ACKED_KEY = 'lightstep_acked_events'

function readAcked() {
	try {
		const raw = uni.getStorageSync(ACKED_KEY)
		const list = typeof raw === 'string' ? JSON.parse(raw) : raw
		return Array.isArray(list) ? list : []
	} catch (e) {
		return []
	}
}

function writeAcked(list) {
	try {
		uni.setStorageSync(ACKED_KEY, JSON.stringify(list.slice(-200)))
	} catch (e) {
		/* ignore */
	}
}

export const useToday = defineStore('today', {
	state: () => ({
		/** 'memo' | 'executing' */
		state: 'memo',
		revision: 0,
		date: '',
		todayDate: '',
		availableDates: [],
		items: [],
		focus: null,
		/** 待澄清的任务：[{ id, title, question }]（后端 PR #16 新增字段） */
		clarifications: [],
		/** 现在能不能进专注（还有未澄清的任务时为 false） */
		canEnterFocus: true,
		suggestedItemId: '',
		reply: '',
		allCompleted: false,
		todayAllCompleted: false,
		navigation: { sidebar_locked: false, can_collapse_focus: true },
		/** 最近一次的事件（receipt / daily_journal） */
		events: [],
		/**
		 * 表现素材策略（2026-11-08 后端新增字段）：
		 * { catalogue_url:'/api/assets/manifest', idle_timeout_seconds:300, idle_effect:'pet_image_only' }
		 */
		presentationPolicy: null,
		/** 最近一次操作结果：{ request_id, status, error } */
		operation: null,
		/**
		 * 备忘录里点了一项、但后端要求先澄清时暂存：
		 * { itemId, question }。备忘录页不放输入框，所以把问题带到专注模式，
		 * 由那里的聊天框回答（见 pages/focusmode）。
		 */
		pendingSelect: null,
		/** 正在等后端 */
		busy: false,
		/** 错误文案 */
		lastError: '',
		/** 有没有加载过 */
		loaded: false
	}),

	actions: (state) => {
		const user = useUser()

		function uid() {
			return user.current()
		}

		/** 把后端返回的清单视图整块覆盖进来（低 revision 不覆盖高 revision） */
		function apply(view) {
			if (!view || typeof view !== 'object') return
			if (view.capture && !('items' in view)) {
				state.operation = view.operation || null
				if (typeof view.revision === 'number') state.revision = Math.max(state.revision, view.revision)
				return
			}
			if (typeof view.revision === 'number' && view.revision < state.revision) return
			state.state = view.state || 'memo'
			if (typeof view.revision === 'number') state.revision = view.revision
			state.date = view.date || state.date
			state.todayDate = view.today_date || state.todayDate
			state.availableDates = Array.isArray(view.available_dates) ? view.available_dates : []
			state.items = Array.isArray(view.items) ? view.items : []
			state.focus = view.focus || null
			// PR #16 新增：待澄清清单 + 是否可进专注
			state.clarifications = Array.isArray(view.clarifications) ? view.clarifications : []
			state.canEnterFocus = view.can_enter_focus !== false
			state.suggestedItemId = view.suggested_item_id || ''
			state.reply = view.reply || ''
			state.allCompleted = !!view.all_completed
			state.todayAllCompleted = !!view.today_all_completed
			if (view.navigation) state.navigation = view.navigation
			state.events = Array.isArray(view.events) ? view.events : []
			// 2026-11-08：表现素材策略（空闲换走神图的秒数等）
			if (view.presentation_policy) state.presentationPolicy = view.presentation_policy
			state.operation = view.operation || null
			state.loaded = true
		}

		/** 统一包一层：网络/业务错误落到 lastError，不抛到页面 */
		async function wrap(fn) {
			if (state.busy) return null
			state.busy = true
			state.lastError = ''
			try {
				const view = await fn()
				apply(view)
                if (view?.operation?.status === 'failed') state.lastError = view.operation.error?.message || view.reply || '这次操作未成功，请重试'
				return view
			} catch (e) {
				state.lastError = (e && e.message) || '没连上，等会儿再试'
				return null
			} finally {
				state.busy = false
			}
		}

        // Persist an operation ID before sending; a lost response retries the same mutation.
        function mutation(action, values) {
            const signature = JSON.stringify({ action, ...values, intent_revision: action === 'select' ? state.revision : undefined })
            const key = 'lightstep_focus_mutation_' + uid() + '_' + action
            const raw = uni.getStorageSync(key)
            const old = raw ? JSON.parse(raw) : null
            const request_id = old && old.signature === signature ? old.id : newRequestId()
            uni.setStorageSync(key, JSON.stringify({ signature, id: request_id }))
            return api.todayCommand({ user_id: uid(), request_id, action, ...values })
        }

		return {
			/** 读清单（可选指定某天的保留清单） */
			async load(date) {
				return wrap(() => api.today(uid(), date))
			},

			/**
			 * 普通对话（PR #16 起 /api/chat 走的是 chat 路由，不再是 intake）：
			 * 后端会自己判断这条消息是「闲聊 / 回答某个待澄清问题 / 新任务」，
			 * 所以前端不需要区分，把用户的话原样发过去即可。
			 * 响应里带 clarifications / can_enter_focus，用于决定能不能进专注。
			 */
			async chat(text) {
				const t = String(text || '').trim()
				if (!t) return null
				return wrap(() => api.chat(uid(), t, { request_id: newRequestId() }))
			},

			/** 发一句话让它识别出多条任务（不开始专注） */
			async intake(text) {
				const t = String(text || '').trim()
				if (!t) return null
				return wrap(() =>
					api.todayCommand({
						user_id: uid(),
						request_id: newRequestId(),
						action: 'intake',
						text: t
					})
				)
			},

			/**
			 * 选中某一项 → 生成/复用森林并开始专注。
			 * 返回 needs_clarification 时，用 answer 再调一次（新的 request_id）。
			 */
			async select(itemId, answer) {
                const values = { item_id: itemId }
                if (answer) values.answer = String(answer).trim()
                return wrap(() => mutation('select', values))
            },

			/**
			 * 调整顺序。
			 * 协议要求 item_ids 恰好包含该日全部未完成项，并带当前 revision；
			 * revision 过期会 409，调用方应重新 load 再试。
			 */
			async reorder(itemIds) {
				const ids = Array.isArray(itemIds) ? itemIds : []
				return wrap(() =>
					api.todayCommand({
						user_id: uid(),
						request_id: newRequestId(),
						action: 'reorder',
						date: state.date,
						revision: state.revision,
						item_ids: ids
					})
				)
			},

			/** 完成当前展示范围（整项完成才会把清单项划掉） */
			async complete(stepId) {
                const f = state.focus
                if (!f) return null
                return wrap(() => mutation('complete', { session_id: f.session_id,
                    step_id: stepId || (f.step && f.step.step_id) }))
            },

			/** 轻一点 / 重一点 */
			async resize(direction, stepId) {
				const f = state.focus
				if (!f) return null
				return wrap(() =>
					api.todayCommand({
						user_id: uid(),
						request_id: newRequestId(),
						action: 'resize',
						session_id: f.session_id,
						step_id: stepId || (f.step && f.step.step_id),
						direction
					})
				)
			},

			/** 中途结束本轮（保留森林与进度，回备忘录） */
			async end() {
                const f = state.focus
                if (!f) return null
                return wrap(() => mutation('end', { session_id: f.session_id }))
            },

			/** 专注页里新增任务（右下角小布那种入口） */
			async capture(text) {
				const f = state.focus
				if (!f) return null
				const t = String(text || '').trim()
				if (!t) return null
				return wrap(() =>
					api.focusCapture({
						user_id: uid(),
						request_id: newRequestId(),
						action: 'focus_capture',
						session_id: f.session_id,
						text: t
					})
				)
			},

			/**
			 * 确认事件已处理。重复 ack 安全。
			 * 同时把 id 记本地，避免同一事件重复建回执条目。
			 */
			async ack(eventId) {
				if (!eventId) return null
				const acked = readAcked()
				if (acked.indexOf(eventId) >= 0) return null
				const view = await wrap(() =>
					api.todayCommand({
						user_id: uid(),
						request_id: newRequestId(),
						action: 'ack',
						event_id: eventId
					})
				)
				if (!view || view.operation?.status !== 'succeeded') return view
				acked.push(eventId)
				writeAcked(acked)
				return view
			},

			/** 事件是否已处理过（本地幂等用） */
			isAcked(eventId) {
				return readAcked().indexOf(eventId) >= 0
			},

			/** 有没有正在专注 */
			hasFocus() {
				return !!(state.focus && state.focus.session_id)
			},

			/** 有没有还没澄清完的任务 */
			hasClarifications() {
				return Array.isArray(state.clarifications) && state.clarifications.length > 0
			},

			/** 第一个待澄清的问题（用于在专注模式里提示用户答什么） */
			firstClarification() {
				return state.clarifications && state.clarifications.length ? state.clarifications[0] : null
			},

			/** 剩余步骤文字（专注模式列表的数据源） */
			remainingActions() {
				const f = state.focus
				const p = f && f.progress
				return p && Array.isArray(p.remaining_actions) ? p.remaining_actions : []
			},

			/** 已完成步骤文字 */
			completedActions() {
				const f = state.focus
				const p = f && f.progress
				return p && Array.isArray(p.completed_actions) ? p.completed_actions : []
			},

			/**
			 * 当前专注项的表现数据（桌宠 + 该印的票根）。
			 * 形如 { available, completed_steps, step_number, normal_stage, normal_pet, receipt, … }
			 * 后端没给（旧数据）时返回 null，页面用中性缺图。
			 */
			focusPresentation() {
				const f = state.focus
				return (f && f.presentation) || null
			},

			/** 某一项的 presentation（备忘录列表用） */
			itemPresentation(itemId) {
				const item = (state.items || []).find((x) => x.id === itemId)
				return (item && item.presentation) || null
			},

			/** 表现素材策略（空闲秒数等） */
			policy() {
				return state.presentationPolicy || null
			},

			/**
			 * 换用户 / 需要重来时把内存里的清单视图清空。
			 *
			 * ⚠️ 必须同时把 revision 归零：apply() 有「低 revision 不覆盖高 revision」的守卫，
			 * 换人后新用户的 revision 是 0，不清零的话那份空清单会被丢掉，
			 * 页面上还留着上一个人的任务（实测就是这样）。
			 * 只清本地视图，不动后端数据（后端按 user_id 隔离）。
			 */
			reset() {
				state.state = 'memo'
				state.revision = 0
				state.date = ''
				state.todayDate = ''
				state.availableDates = []
				state.items = []
				state.focus = null
				state.clarifications = []
				state.canEnterFocus = true
				state.suggestedItemId = ''
				state.reply = ''
				state.allCompleted = false
				state.todayAllCompleted = false
				state.navigation = { sidebar_locked: false, can_collapse_focus: true }
				state.events = []
				state.presentationPolicy = null
				state.operation = null
				state.pendingSelect = null
				state.busy = false
				state.lastError = ''
				state.loaded = false
			},

			/** 清掉「哪些事件已经处理过」的本地去重记录（换用户 / 清手账时用） */
			clearEventCache() {
				try {
					uni.removeStorageSync(ACKED_KEY)
				} catch (e) {
					/* ignore */
				}
			}
		}
	}
})
