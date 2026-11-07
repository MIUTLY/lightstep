/**
 * 错误码 / HTTP 状态码映射。
 *
 * 后端是 FastAPI + Pydantic，没有自定义业务码，实际会出现的只有：
 *  - 422：Pydantic 校验失败，body 形如 {"detail":[{"loc":["body","user_id"],"msg":"...","type":"..."}]}
 *  - 500：未捕获异常，body 形如 {"detail":"Internal Server Error"}
 *  - 404：路径不存在（拼错接口时）
 * 前端按 HTTP status 归类提示，并保留原始 detail 方便排查。
 */

export class ApiError extends Error {
	constructor(message, options = {}) {
		super(message)
		this.name = 'ApiError'
		/** HTTP 状态码，网络层失败时为 0 */
		this.status = options.status || 0
		/** 后端返回的 detail 原文（对象或字符串） */
		this.detail = options.detail || null
		/** 出错时请求的路径 */
		this.url = options.url || ''
		/** 'network' | 'timeout' | 'http' | 'parse' */
		this.kind = options.kind || 'http'
	}
}

const STATUS_TEXT = {
	400: '这句请求小步没听懂，换个说法再试。',
	401: '身份过期了，重新打开一下小程序。',
	403: '这一步暂时没有权限。',
	404: '找不到这条记录，可能已经被删掉了。',
	405: '接口方式不对（前端调用错了方法）。',
	409: '状态冲突了，回到首页刷新一下。',
	422: '参数格式不对，检查一下再试。',
	429: '慢一点，小步有点跟不上了。',
	500: '小步这边出了点状况，等一下再试。',
	502: '后端没起来，确认 python run.py 在跑。',
	503: '后端没起来，确认 python run.py 在跑。'
}

/** 把 FastAPI 的 422 detail 数组拼成一句人话 */
function formatValidationDetail(detail) {
	if (!Array.isArray(detail)) return ''
	return detail
		.map((item) => {
			const field = Array.isArray(item.loc) ? item.loc.filter((x) => x !== 'body').join('.') : ''
			return field ? `${field}：${item.msg}` : item.msg
		})
		.filter(Boolean)
		.join('；')
}

/** FastAPI / Starlette 自带的通用英文短语，不值得直接甩给用户 */
const GENERIC_DETAILS = [
	'Not Found',
	'Method Not Allowed',
	'Internal Server Error',
	'Bad Request',
	'Unprocessable Entity',
	'Service Unavailable'
]

export function messageForStatus(status, detail) {
	if (status === 422) {
		const extra = formatValidationDetail(detail)
		return extra ? `参数格式不对：${extra}` : STATUS_TEXT[422]
	}
	if (
		typeof detail === 'string' &&
		detail &&
		GENERIC_DETAILS.indexOf(detail) < 0
	) {
		return detail
	}
	return STATUS_TEXT[status] || `请求失败（${status}）`
}

export const NETWORK_MESSAGE = '没连上小步。确认后端已在 8000 端口启动，并勾选「不校验合法域名」。'
export const TIMEOUT_MESSAGE = '小步想太久了。再试一次，或者先把任务说短一点。'
