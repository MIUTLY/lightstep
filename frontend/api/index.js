/**
 * 后端接口封装（与 lightstep-backend/app/main.py 一一对应，共 16 个）
 *
 * 统一约定
 * ---------
 * - 写操作一律 POST + JSON body，读操作一律 GET + query。
 * - 每个请求都必须带 user_id（后端没有登录态，user_id 就是身份）。
 * - 绝大多数接口返回同一个结构 Reply：
 *     {
 *       reply:          string,       小步这一句台词（可能为空串）
 *       state:          string,       'idle' | 'ready' | 'committing' | 'executing' | 'done'
 *       buttons:        string[],     后端建议的按钮文案（中文标签，前端按标签映射动作）
 *       task:           TaskView|null 当前任务快照
 *       notes_to_recall:string[],     想起来的便签内容（后端目前只在内部拼进 reply，字段常为空）
 *       due_reminders:  string[],     到点的提醒文案
 *       summary:        string|null   今日小结（收尾 / 完成时才有）
 *     }
 *   其中 TaskView = {
 *       title:         string,
 *       current_step:  string,       当前这一步（snake_case，前端保持同名）
 *       steps_done:    number,       已完成小步数
 *       granularity:   'fine'|'normal'|'coarse',   粒度（摩擦地图调档结果）
 *       state:         string
 *     }
 * - 字段命名：后端用 snake_case，前端状态层一律沿用后端原名（current_step / steps_done /
 *   due_reminders），避免出现两套叫法；只有纯前端状态用 camelCase。
 */
import { del, get, post } from './request.js'

/* ---------------- 会话 ---------------- */

/** 打开 / 每日问候（会顺带做跨天清理，返回跨天交接提示） */
export function openSession(user_id) {
	return post('/api/session/open', { user_id })
}

/** 自由对话（意图识别入口：建任务 / 收尾 / 换事 / 记笔记 / 发呆 / 情绪兜底） */
export function chat(user_id, message) {
	return post('/api/chat', { user_id, message })
}

/** 当前状态（不产生任何副作用，用于冷启动恢复） */
export function sessionState(user_id) {
	return get('/api/session/state', { user_id })
}

/* ---------------- 任务流程 ---------------- */

/** 选择开始时间：when = 'now' | 'later' | 'not_today'（later = 后端固定 30 分钟后提醒） */
export function chooseTime(user_id, when) {
	return post('/api/task/choose_time', { user_id, when })
}

/** 5 分钟轻承诺：agree = true（行）/ false（再想想） */
export function commit(user_id, agree) {
	return post('/api/task/commit', { user_id, agree })
}

/** 完成一小步；duration_ms = 这一步的实际耗时（毫秒），决定下一步加量 / 拆细 */
export function stepComplete(user_id, duration_ms) {
	return post('/api/step/complete', { user_id, duration_ms })
}

/** 太重了 / 太简单：direction = 'smaller' | 'bigger' */
export function stepResize(user_id, direction) {
	return post('/api/step/resize', { user_id, direction })
}

/** 温柔收尾（无惩罚退出，后端会清空当前任务并写一份回执到手帐） */
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

/* ---------------- 手帐 ---------------- */

/** 手帐列表：[{ id, date, steps_done, titles: string[], note, created_at }] */
export function journalList(user_id) {
	return get('/api/journal', { user_id })
}

/** 手帐新增（note 可为空串） */
export function journalAdd(user_id, note) {
	return post('/api/journal/add', { user_id, note })
}

/** 手帐删除（路径参数 entry_id + query user_id） */
export function journalDelete(entry_id, user_id) {
	return del('/api/journal/' + entry_id, { user_id })
}

/* ---------------- 查询 ---------------- */

/** 历史：只记做了什么 [{ date, title }]，最多 30 条 */
export function historyList(user_id) {
	return get('/api/history', { user_id })
}

/** 今日小结：{ date, steps_done, titles: string[] } */
export function dailySummary(user_id) {
	return get('/api/daily/summary', { user_id })
}
