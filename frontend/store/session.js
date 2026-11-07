import { defineStore } from './defineStore.js'
import { useUser } from './user.js'
import * as api from '@/api/index.js'
import { displayLabel, safeDuration } from '@/utils/format.js'

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

/**
 * 后端按钮文案 → 前端动作
 *
 * 计时取消后，后端的「开始时间」只剩两个按钮：现在开始 / 今天不做。
 * （in_5_minutes / in_10_minutes / later 现在返回 410 TASK_TIMERS_REMOVED，所以旧映射已删。）
 */
const LABEL_ACTIONS = {
	现在开始: { type: 'choose_time', when: 'now' },
	今天不做: { type: 'choose_time', when: 'not_today' },
	行: { type: 'commit', agree: true },
	再想想: { type: 'commit', agree: false },
	完成这一步: { type: 'step_complete' },
	太重了: { type: 'resize', direction: 'smaller' },
	太简单了: { type: 'resize', direction: 'bigger' },
	今天到这吧: { type: 'exit' },
	接着做: { type: 'handoff_resume' },
	翻篇: { type: 'handoff_dismiss' },
	/* 任务森林生成失败时后端会在 buttons 前面加这个，点了就带 generation_id 重试 */
	重试生成: { type: 'retry_generation' }
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
		/**
		 * 用户有没有说过话。
		 * 对话页靠它判断是否展示「居中小猫 + 我们要开始做什么呢？」的初始态：
		 * 一旦说过话（哪怕之后被温柔收尾清空了界面）就不再回到初始态。
		 */
		hasTalked: false,
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
		/**
		 * 任务森林生成草稿（Reply.generation）。
		 * { generation_id, status: 'draft'|'succeeded'|'needs_clarification'|'failed',
		 *   goal, question, error, answers, updated_at }
		 * needs_clarification 时用来把输入框切成「补充：」模式；
		 * failed 时用 generation_id 调 retryGeneration()。
		 */
		generation: null,
		/** 页面跳转意图：'focus' | 'chat' | null，由页面消费后清空 */
		navIntent: null,
		/** 最近一次错误文案 */
		lastError: '',
		/** 冷启动是否已 open 过 */
		opened: false
	}),

	actions: (state) => {
		const user = useUser()

		function uid() {
			return user.current()
		}

		function pushCat(reply) {
			state.messages.push({ id: nextId(), role: 'cat', reply })
		}

		function pushUser(text) {
			state.hasTalked = true
			state.messages.push({ id: nextId(), role: 'user', text })
		}

		function pushSystem(text) {
			state.messages.push({ id: nextId(), role: 'system', text })
		}

		/**
		 * 计时身份：后端从「保留动作顺序」那一版开始给每个动作一个稳定标识 step_id
		 * （形如 "3f2a...:s0"），比「标题+文字」可靠 —— 粒度切换后可能有两步文字相同、
		 * 但它们是不同的动作，按文字判断会漏掉重置计时或错误重置。
		 * 老后端没有 step_id，退回用 title|current_step 作键。
		 */
		function syncStepTimer(task) {
			if (task && task.state === 'executing') {
				const key = task.step_id ? task.step_id : task.title + '|' + task.current_step
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
			// 任务森林生成草稿：succeeded 时后端也会带上，用来在失败后重试
			state.generation = reply.generation || null
			syncStepTimer(state.task)

			if (!opts.silent) pushCat(reply)

			// 跳转意图：进入执行态 → 去单步页；离开执行态 → 回对话页
			if (state.state === 'executing' && prevState !== 'executing') {
				state.navIntent = 'focus'
			} else if (prevState === 'executing' && state.state !== 'executing') {
				state.navIntent = 'chat'
			}
		}

		/** 包一层错误处理：网络/后端错误只推一条系统小字，不打断对话 */
		async function run(fn) {
			if (state.busy) return null
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

		return {
			displayLabel,

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
				if (action.type === 'retry_generation') {
					await this.retryGeneration()
					return
				}
			},

			/**
			 * 「先把这一段开起来」：ready → 现在开始 → committing → 行 → executing。
			 * 专注模式里点「完成了」时如果任务还没开始，就用它一步推进到执行态，
			 * 否则会撞上后端 409 INVALID_TASK_STATE（实测：ready 下调 /api/step/complete 会 409）。
			 */
			async startExecuting() {
				if (state.state === 'ready') {
					const r1 = await run(() => api.chooseTime(uid(), 'now'))
					if (!r1) return
					applyReply(r1)
				}
				if (state.state === 'committing') {
					const r2 = await run(() => api.commit(uid(), true))
					if (r2) applyReply(r2)
				}
			},

			/** 完成这一步：把真实耗时 + 当前步的 step_id 一起回传 */
			async completeStep() {
				const duration = state.stepStartedAt
					? safeDuration(Date.now() - state.stepStartedAt)
					: 30000
				const stepId = state.task ? state.task.step_id : ''
				const reply = await run(() => api.stepComplete(uid(), duration, stepId))
				if (reply) applyReply(reply)
			},

			/** 太重了 / 太简单（同样带上 step_id，让后端确认改的是同一动作） */
			async resize(direction) {
				const stepId = state.task ? state.task.step_id : ''
				const reply = await run(() => api.stepResize(uid(), direction, stepId))
				if (reply) applyReply(reply)
			},

			/**
			 * 生成失败后重试（按钮「重试生成」）。
			 * needs_clarification 时后端要求先回答澄清问题，这里会失败并给 409 —— 所以只在 failed 时可用。
			 */
			async retryGeneration() {
				const g = state.generation
				if (!g || !g.generation_id) {
					pushSystem('没有可重试的生成记录，重新说一遍目标就行。')
					return
				}
				const reply = await run(() => api.retryGeneration(uid(), g.generation_id))
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
				try {
					const data = await api.sessionState(uid())
					state.state = data.state || 'idle'
					state.task = data.task || null
					syncStepTimer(state.task)
					return data
				} catch (e) {
					return null
				}
			},

			/**
			 * 轮询「预约开始」提醒（后端 5/10 分钟预约机制）。
			 *
			 * 后端用 task.start_due_at 记下到点时间，前端需要定时 POST /api/reminders/poll：
			 *  - 未到点：reply 为空串、due_reminders 为 []，什么都不用做
			 *  - 已到点：due_reminders 里有提醒文案（并已从后端队列取出，只发一次）
			 *
			 * 返回 true 表示这次真的收到提醒（页面可以据此停止轮询）。
			 */
			async pollStartReminder() {
				if (!state.task || !state.task.start_due_at) return false
				if (state.busy) return false
				try {
					const reply = await api.pollReminders(uid())
					const due = reply && Array.isArray(reply.due_reminders) ? reply.due_reminders : []
					state.state = reply.state || state.state
					state.task = reply.task || null
					syncStepTimer(state.task)
					if (!due.length) return false
					state.reminders = due
					// reply.reply 此时是空串，这里补一句「轻轻提醒」的语气，再交给气泡渲染
					pushCat(Object.assign({}, reply, { reply: due.join('；') }))
					return true
				} catch (e) {
					return false
				}
			},

			/** 有没有正在等待的预约（决定对话页要不要显示那一行小字 + 轮询） */
			hasStartReminder() {
				return !!(state.task && state.task.start_due_at)
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
