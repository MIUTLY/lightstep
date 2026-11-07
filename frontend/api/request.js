/**
 * uni.request 统一封装。
 *
 * 职责：
 *  1. 拼 URL（可运行时覆盖 baseUrl，方便换真机联调）
 *  2. 统一注入请求头（含鉴权位；后端暂无鉴权，见下方 buildAuthHeaders 注释）
 *  3. 统一超时 / 网络错误 / HTTP 错误 → 抛出 ApiError（带 status、detail、kind）
 *  4. 统一 toast 提示（silent: true 时可静默，由页面自己处理）
 *
 * 注意：后端所有接口都是「无状态 + user_id 明确传参」，
 * 前端不需要 cookie / session，也不需要刷新 token。
 */
import { APP_VERSION, DEFAULT_BASE_URL, REQUEST_TIMEOUT, STORAGE_KEYS } from '@/config/index.js'
import { ApiError, NETWORK_MESSAGE, TIMEOUT_MESSAGE, messageForStatus } from './errors.js'

/** 当前后端地址（本地缓存可覆盖默认值，见设置页「长按版本号」） */
export function getBaseUrl() {
	const override = uni.getStorageSync(STORAGE_KEYS.baseUrl)
	const raw = String(override || DEFAULT_BASE_URL).trim()
	return raw.replace(/\/+$/, '')
}

/** 写入运行时后端地址；传空字符串表示恢复默认 */
export function setBaseUrl(url) {
	const raw = String(url || '').trim().replace(/\/+$/, '')
	if (!raw) {
		uni.removeStorageSync(STORAGE_KEYS.baseUrl)
		return
	}
	uni.setStorageSync(STORAGE_KEYS.baseUrl, raw)
}

/**
 * 鉴权头。
 * 后端 lightstep-backend 目前没有任何登录 / token 接口（README「不做的功能」里明确写了不做账号系统），
 * 身份就是客户端本地生成并长期保存的 user_id，随每次请求的 body / query 传过去。
 * 这里预留 Authorization 位：后端将来加 JWT 时，只要登录流程把 token 写进
 * 本地缓存 'lightstep_token'，所有请求会自动带上，不用改接口层。
 */
function buildAuthHeaders() {
	const headers = {}
	const token = uni.getStorageSync('lightstep_token')
	if (token) headers.Authorization = 'Bearer ' + token
	return headers
}

function buildQuery(query) {
	const parts = []
	Object.keys(query).forEach((key) => {
		const value = query[key]
		if (value === undefined || value === null) return
		parts.push(encodeURIComponent(key) + '=' + encodeURIComponent(value))
	})
	return parts.length ? '?' + parts.join('&') : ''
}

function parseBody(data) {
	if (data === null || data === undefined || data === '') return null
	if (typeof data === 'object') return data
	try {
		return JSON.parse(data)
	} catch (e) {
		return data
	}
}

/**
 * @param {Object} options
 * @param {string} options.url      以 / 开头的路径，例如 '/api/chat'
 * @param {string} [options.method] GET / POST / DELETE
 * @param {Object} [options.data]   请求体（JSON）
 * @param {Object} [options.query]  查询参数（会做 url encode）
 * @param {boolean} [options.silent] 出错时不弹 toast
 */
export function request(options) {
	const { url, method = 'GET', data = null, query = null, silent = false } = options
	const fullUrl = getBaseUrl() + url + (query ? buildQuery(query) : '')

	return new Promise((resolve, reject) => {
		uni.request({
			url: fullUrl,
			method,
			data: data || undefined,
			timeout: REQUEST_TIMEOUT,
			header: Object.assign(
				{
					'Content-Type': 'application/json',
					'X-LightStep-Client': 'mini/' + APP_VERSION
				},
				buildAuthHeaders()
			),
			success: (res) => {
				const body = parseBody(res.data)
				const status = res.statusCode || 0

				if (status >= 200 && status < 300) {
					resolve(body)
					return
				}

				const detail = body && body.detail !== undefined ? body.detail : body
				const error = new ApiError(messageForStatus(status, detail), {
					status,
					detail,
					url,
					kind: 'http'
				})
				if (!silent) uni.showToast({ title: error.message, icon: 'none', duration: 2600 })
				reject(error)
			},
			fail: (err) => {
				const errMsg = (err && err.errMsg) || ''
				const isTimeout = errMsg.indexOf('timeout') >= 0
				const error = new ApiError(isTimeout ? TIMEOUT_MESSAGE : NETWORK_MESSAGE, {
					status: 0,
					detail: errMsg,
					url,
					kind: isTimeout ? 'timeout' : 'network'
				})
				if (!silent) uni.showToast({ title: error.message, icon: 'none', duration: 3000 })
				reject(error)
			}
		})
	})
}

export function get(url, query, options = {}) {
	return request(Object.assign({ url, query, method: 'GET' }, options))
}

export function post(url, data, options = {}) {
	return request(Object.assign({ url, data, method: 'POST' }, options))
}

export function del(url, query, options = {}) {
	return request(Object.assign({ url, query, method: 'DELETE' }, options))
}
