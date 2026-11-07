/**
 * 运行时配置（唯一需要改的联调入口）
 *
 * 后端默认起在 http://127.0.0.1:8000（见 lightstep-backend/run.py）。
 *  - 微信开发者工具：需勾选「详情 → 本地设置 → 不校验合法域名…」，否则 http 请求被拦。
 *  - 真机预览：把 baseUrl 改成电脑的局域网 IP，例如 http://192.168.1.8:8000，
 *    并让 run.py 监听 0.0.0.0（uvicorn --host 0.0.0.0）。
 *  - 也可以在「设置」页长按版本号临时改地址（写入本地缓存，覆盖此处默认值）。
 */

export const APP_VERSION = '1.0.0'

/** 后端地址（不带结尾斜杠） */
export const DEFAULT_BASE_URL = 'http://127.0.0.1:8000'

/** 请求超时（毫秒）。LLM 真调用时后端最慢 30s，这里留一点余量。 */
export const REQUEST_TIMEOUT = 35000

/** 本地缓存键（统一前缀，便于「清空本地身份」一次清干净） */
export const STORAGE_KEYS = {
	userId: 'lightstep_user',
	settings: 'lightstep_settings',
	baseUrl: 'lightstep_baseurl'
}
