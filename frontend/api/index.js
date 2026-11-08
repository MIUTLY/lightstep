/**
 * 后端接口封装
 *
 * 对齐的是 MIUTLY/lightstep 仓库 2026-11-07 之后的 backend/（含 PR #8 五分钟/十分钟预约）。
 *
 * ⚠️ 2026-11-08 后端升级到 main@0f2e84e7（PR #17「对外文案过滤」+「只记录行动进度、不验收成果」）：
 *   - 展示字段（reply / current_step / question / summary / feedback / title / scope）已由后端统一过滤，
 *     「（本次对话：…）」「（内部备注：…）」这类内部说明不会再下发；前端不要自己再删一遍，
 *     也不要用完整父标题去重建任务文案。
 *   - 父任务的 current_step 会把动作明细并进同一字段，用 **换行** 分隔
 *     （「洗衣服\n放入衣物；加洗衣液」），渲染时必须保留换行。
 *   - 拆分只记录用户自报进度，不检查正确率/不要求留证或交答案；界面不要出现「上传 / 验收 / 正确率」。
 *   - 结构、字段名、接口参数均未变化。
 *
 * ⚠️ 2026-11-08 再次升级到 main@b8e6e026（PR #20「每项任务的表现计步 + 公共素材托管」）：
 *   - 新增 `presentation_completed_steps`：每项任务独立计步，成功 complete 才 +1（resize/打开/退出都不加），
 *     与森林的 completed_leaf_ids 互相独立，**前端不许用叶子数或 steps_done 自己推票根**。
 *   - `items[].presentation`、`focus.presentation`、旧的 `TaskView.presentation`、以及 receipt 事件的
 *     `presentation` 都是同一结构：
 *       { available, completed_steps, step_number, normal_stage, normal_pet:{url,width,height},
 *         receipt:{id,url,preview:{url},composition:{…}}, source, asset_version }
 *     数据不足时 available=false、step_number/receipt 为 null —— 这时用中性缺图，别随机挑票根。
 *   - 新增 `presentation_policy`：{ catalogue_url:'/api/assets/manifest', idle_timeout_seconds:300,
 *     idle_effect:'pet_image_only' }。
 *   - 新增 `GET /api/assets/manifest` 与静态素材 `/api/assets/v1/**`（内容哈希 + 一年不可变缓存）。
 *     素材地址用 `assetUrl()` 拼，别和带 /api 的基地址重复拼。
 *   - receipt 事件新增 `occurred_date`（Asia/Shanghai 实际结束日）与 `presentation`；
 *     原 `date` 是清单归属日。手账归档按 `occurred_date`。
 *   - 协议细节见仓库 docs/task-presentation-assets.md。
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
import { getBaseUrl } from './request.js'
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
export async function chat(user_id, message, opts = {}) {
	const body = { user_id, message }
	if (opts.workflow) body.workflow = opts.workflow
	// 默认流程必须带 request_id；legacy 不需要
	if (opts.request_id) body.request_id = opts.request_id
	else if (opts.workflow !== 'legacy') body.request_id = newRequestId()

	const startedAt = Date.now()
	try {
		const first = await post('/api/chat', body)
		if (!retryableChatFailure(first) || Date.now() - startedAt > CHAT_RETRY_QUICK_ENOUGH) return first
		// 后端 200 但操作失败（典型是 AI_CONNECTION_FAILED，retryable=true）：
		// 换一个新的 request_id 重发一次 —— 失败的那次数据已回滚，重跑不会重复建任务
		await sleep(CHAT_RETRY_DELAY)
		return post('/api/chat', Object.assign({}, body, { request_id: newRequestId() }))
	} catch (error) {
		// 压根没拿到响应（断网 / 超时 / 5xx）：用同一个 request_id 再问一次，
		// 服务端若其实已经成功会直接回放缓存结果，不会重复建任务
		if (!retryableChatTransport(error) || Date.now() - startedAt > CHAT_RETRY_QUICK_ENOUGH) throw error
		await sleep(CHAT_RETRY_DELAY)
		return post('/api/chat', body)
	}
}

/** 上一次对话请求"失败得够快"才值得自动重试：太慢的话重试只会一起超时 */
const CHAT_RETRY_QUICK_ENOUGH = 20000
const CHAT_RETRY_DELAY = 900

/** 后端回了话，但这次操作是失败且可重试的（例如 AI 连接被重置） */
function retryableChatFailure(view) {
	const op = view && view.operation
	return !!(op && op.status === 'failed' && op.error && op.error.retryable)
}

/** 连响应都没拿到：网络层错误或 5xx */
function retryableChatTransport(error) {
	if (!error) return false
	if (error.kind === 'network' || error.kind === 'timeout') return true
	return (Number(error.status) || 0) >= 500
}

function sleep(ms) {
	return new Promise((resolve) => setTimeout(resolve, ms))
}

/** 当前状态（不产生副作用，用于冷启动恢复） */
export function sessionState(user_id) {
	return get('/api/session/state', { user_id })
}

/** 存活检查：{ status, storage, receipt_storage } */
export function health() {
	return get('/api/health')
}

/* ---------------- 公共素材（2026-11-08 起由后端托管） ---------------- */

/**
 * 素材清单：{ version, pets, receipts, journal, idle_policy, receipt_selection }
 *
 * - pets：6 张桌宠状态图（initial / starting / flow / reward / distracted / emergency_dark）
 * - receipts：12 张票根（1.1~4.3），每张带 url / preview / composition（印字与日期坐标）
 * - journal：大底图目前 available=false（等素材），不要自己画替代底图
 * - idle_policy：前台 300 秒未操作只换走神图，不改任何状态
 */
export function assetsManifest() {
	return get('/api/assets/manifest')
}

/**
 * 把清单里的素材路径拼成可直接加载的地址。
 *
 * 清单里的 url 已经是「含 /api 的绝对路径」（如 /api/assets/v1/pets/initial-xxx.png），
 * 所以只跟服务 origin 拼，不能和带 /api 的基地址重复拼接：
 *   base = http://127.0.0.1:8000        → http://127.0.0.1:8000/api/assets/v1/...
 *   base = http://127.0.0.1:8000/api    → 先去掉 /api 再拼
 */
export function assetUrl(path) {
	if (!path) return ''
	const raw = String(path)
	if (/^https?:\/\//.test(raw)) return raw
	const base = String(getBaseUrl() || '').replace(/\/+$/, '').replace(/\/api$/, '')
	return base + (raw.charAt(0) === '/' ? raw : '/' + raw)
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
 * 注意 needs_clarification 时 **buttons 是空数组**，只能靠用户回「补充：…」（走 /api/chat）。
 * 澄清问的是范围（哪份作业、做成几题），不是要答案或选项——别在 UI 上写成「交答案」。
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
