/**
 * 后端接口封装
 *
 * 对齐的是 MIUTLY/lightstep 仓库 2026-11-07 之后的 backend/（含 PR #8 五分钟/十分钟预约）。
 *
 * 统一约定
 * ---------
 * - 写操作一律 POST + JSON body，读操作一律 GET + query。
 * - 每个请求都必须带 user_id（后端没有登录态，user_id 就是身份）；后端校验非空。
 * - 绝大多数接口返回同一个结构 Reply：
 *     {
 *       reply:          string,       小步这一句台词（可能为空串，例如轮询提醒时）
 *       state:          string,       'idle' | 'ready' | 'committing' | 'executing' | 'done'
 *       buttons:        string[],     后端建议的按钮文案（中文标签，前端按标签映射动作）
 *       task:           TaskView|null 当前任务快照
 *       notes_to_recall:string[],     想起来的便签（后端目前拼进 reply，字段常为空）
 *       due_reminders:  string[],     到点的提醒文案
 *       summary:        string|null   今日小结（收尾 / 完成时才有）
 *     }
 *   其中 TaskView = {
 *       title:         string,
 *       current_step:  string,       当前这一步（snake_case，前端保持同名）
 *       steps_done:    number,
 *       granularity:   'fine'|'normal'|'coarse',
 *       state:         string,
 *       step_id:       string,       当前动作的稳定标识（计时用它判断"换了一步"）
 *       start_due_at:  string|null   预约开始的 UTC ISO 时间；消费/取消后为 null
 *     }
 *
 * ⚠️ 已移除：/api/journal、/api/journal/add、DELETE /api/journal/{id}
 *   后端现在对这三个一律返回 410 detail.code=JOURNAL_CLIENT_ONLY，
 *   手帐改为客户端本地保存，见 utils/localJournal.js。
 */
import { del, get, post } from './request.js'
import { newRequestId } from '@/utils/requestId.js'

/* ---------------- 会话 ---------------- */

/** 打开 / 每日问候（会顺带做跨天清理，返回跨天交接提示） */
export function openSession(user_id) {
	return post('/api/session/open', { user_id })
}

/**
 * 自由对话 / 今日任务识别。
 *
 * ⚠️ 后端 2026-11-07 之后改版：
 *   默认进入「今日备忘录」流程，**必须带 request_id**（否则 422）。
 *   返回的形状也变了（state='memo'、items[]、revision…），不是旧的 Reply。
 *   想走旧的单任务流程，要显式传 workflow:'legacy'。
 *
 * @param {string} user_id
 * @param {string} message
 * @param {{request_id?: string, workflow?: 'today'|'legacy'}} [opts]
 */
export function chat(user_id, message, opts = {}) {
	const body = { user_id, message }
	if (opts.workflow) body.workflow = opts.workflow
	// 默认流程必须带 request_id；legacy 不需要
	if (opts.request_id) body.request_id = opts.request_id
	else if (opts.workflow !== 'legacy') body.request_id = newRequestId()
	return post('/api/chat', body)
}

/** 当前状态（不产生副作用，用于冷启动恢复） */
export function sessionState(user_id) {
	return get('/api/session/state', { user_id })
}

/** 存活检查：{ status, storage, receipt_storage } */
export function health() {
	return get('/api/health')
}

/* ---------------- 今日备忘录（新主流程） ---------------- */

/** 读今日清单；date 可选（YYYY-MM-DD），用于回看保留的某日清单 */
export function today(user_id, date) {
	const query = { user_id }
	if (date) query.date = date
	return get('/api/today', query)
}

/**
 * 今日清单写操作（统一入口）。
 * 公共字段 user_id + request_id；action 为
 * 'intake' | 'reorder' | 'select' | 'resize' | 'complete' | 'end' | 'ack'。
 * 返回 HTTP 200 也可能是业务失败，要看 operation.status。
 */
export function todayCommand(payload) {
	return post('/api/today/command', payload)
}

/** 找回某个 request_id 的原命令和结果 */
export function todayOperation(user_id, request_id) {
	return get('/api/today/operation', { user_id, request_id })
}

/** 最近 50 条持久化操作（用于找回失败请求的原始输入） */
export function todayOperations(user_id) {
	return get('/api/today/operations', { user_id })
}

/** 专注页里新增任务（"再做一件"）；插入与去重由后端负责 */
export function focusCapture(payload) {
	return post('/api/focus/capture', payload)
}

/* ---------------- 旧的单任务流程（workflow=legacy 时才会用到） ---------------- */

/**
 * 选择开始时间。
 * ⚠️ 计时已取消：`in_5_minutes` / `in_10_minutes` 现在返回 **410 TASK_TIMERS_REMOVED**，
 *    只剩 'now' 与 'not_today' 可用。
 */
export function chooseTime(user_id, when) {
	return post('/api/task/choose_time', { user_id, when })
}

/**
 * ⚠️ 已停用：后端返回 410 TASK_TIMERS_REMOVED（"预约提醒已取消，请停止轮询"）。
 * 保留导出只是为了老代码不报错，**不要调用**。
 */
export function pollReminders(user_id) {
	return post('/api/reminders/poll', { user_id })
}

/**
 * 直接生成任务（任务森林）——与 /api/chat 走同一套 _create_task，只是入口更明确。
 * 返回的 Reply 里会带 generation：status 可能是 succeeded / needs_clarification / failed。
 * 注意 needs_clarification 时 **buttons 是空数组**，只能靠用户回「补充：答案」（走 /api/chat）。
 */
export function generateTask(user_id, goal) {
	return post('/api/task/generate', { user_id, goal })
}

/** 当前生成草稿的状态（null 表示没有草稿）；返回 { generation } */
export function generationStatus(user_id) {
	return get('/api/task/generation', { user_id })
}

/** 生成失败后重试（需要 generation_id） */
export function retryGeneration(user_id, generation_id) {
	return post('/api/task/generation/retry', { user_id, generation_id })
}

/** 回答澄清问题后再生成（一般用 /api/chat 发「补充：…」即可，这里留作显式调用） */
export function answerGeneration(user_id, generation_id, answer) {
	return post('/api/task/generation/answer', { user_id, generation_id, answer })
}

/** 5 分钟轻承诺：agree = true（行）/ false（再想想） */
export function commit(user_id, agree) {
	return post('/api/task/commit', { user_id, agree })
}

/**
 * 完成一小步。
 * duration_ms 必须是非负整数（后端 strict=True，浮点会 422）。
 * step_id 取 task.step_id —— 后端用它校验「完成的确实是当前这一步」，
 * 森林模式（plan_format=forest_v1）下不带或带错可能被拒/记错步。
 */
export function stepComplete(user_id, duration_ms, step_id) {
	const body = { user_id, duration_ms }
	if (step_id) body.step_id = step_id
	return post('/api/step/complete', body)
}

/** 太重了 / 太简单：direction = 'smaller' | 'bigger'，同样带上当前步的 step_id */
export function stepResize(user_id, direction, step_id) {
	const body = { user_id, direction }
	if (step_id) body.step_id = step_id
	return post('/api/step/resize', body)
}

/** 温柔收尾（无惩罚退出） */
export function exitTask(user_id, gentle = true) {
	return post('/api/task/exit', { user_id, gentle })
}

/* ---------------- 便签 / 交接 ---------------- */

/** 走神记笔记（不打断当前步骤） */
export function addNote(user_id, content) {
	return post('/api/note', { user_id, content })
}

/** 跨天交接：接着上次做 */
export function resumeHandoff(user_id) {
	return post('/api/handoff/resume', { user_id })
}

/** 跨天交接：翻篇 */
export function dismissHandoff(user_id) {
	return post('/api/handoff/dismiss', { user_id })
}

/* ---------------- 查询 ---------------- */

/** 历史：只记做了什么 [{ date, title }] */
export function historyList(user_id) {
	return get('/api/history', { user_id })
}

/** 今日小结：{ date, steps_done, titles } */
export function dailySummary(user_id) {
	return get('/api/daily/summary', { user_id })
}

/**
 * 手帐接口已停用，这里不导出任何 journal 函数。
 * 如果以后后端恢复，再从这里加回来；当前一律走 utils/localJournal.js。
 */
export const JOURNAL_ENDPOINTS_REMOVED = true

/* del 仍由 request.js 提供给将来的 DELETE 类接口使用 */
export { del }
