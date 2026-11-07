import { defineStore } from './defineStore.js'
import { useUser } from './user.js'
import * as api from '@/api/index.js'
import { displayLabel, safeDuration } from '@/utils/format.js'
import { stepKey } from '@/utils/stepIdentity.js'
import { createStartReminderPoller } from '@/utils/startReminderPoller.js'

/**
 * 会话 store：整个小程序的单一状态源。
 *
 * 设计要点
 * --------
 * 1. 状态字段全部沿用后端命名（state / task / task.current_step / task.steps_done），
 *    只有「纯前端」的东西才用驼峰（stepStartedAt / navIntent / noteMode）。
 * 2. 所有后端调用都走 applyReply()，保证「一条回复 = 一条气泡 + 一次状态同步」，
 *    页面只负责渲染，不各自解析返回值。
 * 3. 按钮不写死：后端在 buttons 里给中文标签，这里按标签映射到具体接口
 *    （LABEL_ACTIONS），遇到不认识的标签就当成一句话发回 /api/chat，
 *    这样后端将来加新按钮文案时前端不会崩。
 * 4. 计时：只有 state === 'executing' 且 current_step 变化时才重置起步时间，
 *    用于回传真实的 duration_ms（自适应粒度的唯一输入）。
 */

/** 后端按钮文案 → 前端动作 */
const LABEL_ACTIONS = {
	现在开始: { type: 'choose_time', when: 'now' },
	待会儿: { type: 'choose_time', when: 'later' },
	'5分钟后': { type: 'choose_time', when: 'in_5_minutes' },
	'10分钟后': { type: 'choose_time', when: 'in_10_minutes' },
	今天不做: { type: 'choose_time', when: 'not_today' },
	行: { type: 'commit', agree: true },
	再想想: { type: 'commit', agree: false },
	完成这一步: { type: 'step_complete' },
	太重了: { type: 'resize', direction: 'smaller' },
	太简单了: { type: 'resize', direction: 'bigger' },
	今天到这吧: { type: 'exit' },
	接着做: { type: 'handoff_resume' },
	翻篇: { type: 'handoff_dismiss' }
}

let seq = 0
function nextId() {
	seq += 1
	return Date.now().toString(36) + '_' + seq
}

export const useSession = defineStore('session', {
	state: () => ({
		/** [{ id, role: 'cat'|'user'|'system', reply?, text? }] */
		messages: [],
		/** 后端返回的会话状态机 */
		state: 'idle',
		/** 当前任务快照（TaskView，可能为 null） */
		task: null,
		/** 是否正在等后端 */
		busy: false,
		/** 输入框是否处于「记笔记」模式 */
		noteMode: false,
		/** 这一步的起步时间戳（ms） */
		stepStartedAt: 0,
		/** 用来判断 current_step 是否换了 */
		lastStepKey: '',
		/** 到点的提醒文案（后端 due_reminders） */
		reminders: [],
		/** 页面跳转意图：'focus' | 'chat' | null，由页面消费后清空 */
		navIntent: null,
		/** 最近一次错误文案 */
		lastError: '',
		/** 冷启动是否已 open 过 */
		opened: false
	}),

	actions: (state) => {
		const user = useUser()
		let operationVersion = 0

		function uid() {
			return user.current()
		}

		function pushCat(reply) {
			state.messages.push({ id: nextId(), role: 'cat', reply })
		}

		function pushUser(text) {
			state.messages.push({ id: nextId(), role: 'user', text })
		}

		function pushSystem(text) {
			state.messages.push({ id: nextId(), role: 'system', text })
		}

		function syncStepTimer(task) {
			if (task && task.state === 'executing') {
				const key = stepKey(task)
				if (key !== state.lastStepKey) {
					state.lastStepKey = key
					state.stepStartedAt = Date.now()
				}
				return
			}
			state.lastStepKey = ''
			state.stepStartedAt = 0
		}

		/**
		 * 统一处理一条 Reply。
		 * @param {Object} reply  后端 Reply
		 * @param {Object} [opts]
		 * @param {boolean} [opts.silent] 不推气泡（只同步状态）
		 * @param {boolean} [opts.keepMessages] 保持已有消息顺序（重置后重放用）
		 */
		function applyReply(reply, opts = {}) {
			if (!reply || typeof reply !== 'object') return
			const prevState = state.state

			state.state = reply.state || 'idle'
			state.task = reply.task || null
			state.reminders = Array.isArray(reply.due_reminders) ? reply.due_reminders : []
			syncStepTimer(state.task)

			if (!opts.silent) pushCat(reply)

			// 跳转意图：进入执行态 → 去单步页；离开执行态 → 回对话页
			if (state.state === 'executing' && prevState !== 'executing') {
				state.navIntent = 'focus'
			} else if (prevState === 'executing' && state.state !== 'executing') {
				state.navIntent = 'chat'
			}
			reminderPoller.refresh()
		}

		/** 包一层错误处理：网络/后端错误只推一条系统小字，不打断对话 */
		async function run(fn) {
			if (state.busy) return null
			operationVersion += 1
			state.busy = true
			state.lastError = ''
			try {
				return await fn()
			} catch (err) {
				state.lastError = err && err.message ? err.message : '出了点状况'
				pushSystem(state.lastError)
				return null
			} finally {
				state.busy = false
			}
		}

		function hasPendingStartReminder() {
			return state.state === 'ready' && !!state.task && !!state.task.start_due_at
		}

		const reminderPoller = createStartReminderPoller(async (isCurrent) => {
			if (state.busy || !hasPendingStartReminder()) return
			const version = operationVersion
			const requestUser = uid()
			const reply = await api.pollStartReminder(requestUser)
			// 用户开始/改约/退出时，旧轮询结果不能恢复旧任务或显示旧提醒。
			if (!isCurrent() || version !== operationVersion || requestUser !== uid() || state.busy) return
			const due = Array.isArray(reply.due_reminders) && reply.due_reminders.length > 0
			applyReply(reply, { silent: !due })
		}, { shouldPoll: hasPendingStartReminder })

		return {
			displayLabel,
			startReminderChecks() { reminderPoller.start() },
			stopReminderChecks() { reminderPoller.stop() },

			/** 冷启动：打开会话（会拿到跨天交接提示 / 上次做到哪） */
			async open(force = false) {
				if (state.opened && !force) return
				const reply = await run(() => api.openSession(uid()))
				if (reply) {
					state.opened = true
					applyReply(reply)
				}
			},

			/** 自由对话 */
			async sendChat(text) {
				const message = String(text || '').trim()
				if (!message || state.busy) return
				pushUser(message)
				const reply = await run(() => api.chat(uid(), message))
				if (reply) applyReply(reply)
			},

			/** 走神记笔记（不打断当前步骤） */
			async sendNote(text) {
				const content = String(text || '').trim()
				if (!content || state.busy) return
				pushUser('（记笔记）' + content)
				const reply = await run(() => api.addNote(uid(), content))
				if (reply) applyReply(reply)
			},

			/**
			 * 点后端给的按钮。
			 * 不认识的标签兜底成一句话（后端 README：「点某句话」也是合法输入）。
			 */
			async dispatchLabel(label) {
				const action = LABEL_ACTIONS[label]
				if (!action) {
					await this.sendChat(label)
					return
				}
				if (action.type === 'choose_time') {
					const reply = await run(() => api.chooseTime(uid(), action.when))
					if (reply) applyReply(reply)
					return
				}
				if (action.type === 'commit') {
					const reply = await run(() => api.commit(uid(), action.agree))
					if (reply) applyReply(reply)
					return
				}
				if (action.type === 'step_complete') {
					await this.completeStep()
					return
				}
				if (action.type === 'resize') {
					await this.resize(action.direction)
					return
				}
				if (action.type === 'exit') {
					await this.exitTask()
					return
				}
				if (action.type === 'handoff_resume') {
					const reply = await run(() => api.resumeHandoff(uid()))
					if (reply) applyReply(reply)
					return
				}
				if (action.type === 'handoff_dismiss') {
					const reply = await run(() => api.dismissHandoff(uid()))
					if (reply) applyReply(reply)
					return
				}
			},

			/** 完成这一步：把真实耗时回传，后端据此决定下一步加量还是拆细 */
			async completeStep() {
				const duration = state.stepStartedAt
					? safeDuration(Date.now() - state.stepStartedAt)
					: 30000
				const reply = await run(() => api.stepComplete(uid(), duration))
				if (reply) applyReply(reply)
			},

			/** 太重了 / 太简单 */
			async resize(direction) {
				const reply = await run(() => api.stepResize(uid(), direction))
				if (reply) applyReply(reply)
			},

			/**
			 * 温柔收尾（无惩罚退出）。
			 * 策划书 F4：不弹确认、不留记录、界面直接清空 —— 所以这里先请求后端，
			 * 拿到收尾台词后把除这一条以外的消息全部清掉。
			 */
			async exitTask() {
				const reply = await run(() => api.exitTask(uid(), true))
				if (!reply) return
				state.messages = []
				state.task = null
				state.lastStepKey = ''
				state.stepStartedAt = 0
				state.state = reply.state || 'idle'
				state.reminders = Array.isArray(reply.due_reminders) ? reply.due_reminders : []
				state.navIntent = 'chat'
				pushCat(reply)
				reminderPoller.refresh()
			},

			/** 拉一次今日小结（回执页用） */
			async fetchTodaySummary() {
				try {
					return await api.dailySummary(uid())
				} catch (e) {
					return null
				}
			},

			/** 拉一次当前状态（冷启动兜底：用户直接杀进程后重进） */
			async syncState() {
				if (state.busy) return null
				const version = ++operationVersion
				const requestUser = uid()
				try {
					const data = await api.sessionState(requestUser)
					if (version !== operationVersion || requestUser !== uid() || state.busy) return null
					state.state = data.state || 'idle'
					state.task = data.task || null
					syncStepTimer(state.task)
					reminderPoller.refresh()
					return data
				} catch (e) {
					return null
				}
			},

			/** 页面消费跳转意图 */
			takeNavIntent() {
				const intent = state.navIntent
				state.navIntent = null
				return intent
			},

			/** 手动设置跳转意图（例如从对话页点「收起来」） */
			setNavIntent(intent) {
				state.navIntent = intent
			},

			/** 彻底清空本地会话视图（不清后端数据） */
			clearMessages() {
				state.messages = []
			}
		}
	}
})

