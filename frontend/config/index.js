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

/**
 * 请求超时（毫秒）。
 *
 * 一次 /api/chat 在服务端要串行调用好几次 DeepSeek（路由 → 任务识别 → 复核 → 逐项范围澄清），
 * 正常 5~10s，但模型端偶发 20~30s 的慢响应，原来的 35s 会抢先超时、
 * 界面只留下一句「小步想太久了」，看起来就像「没反应」。
 * 现在后端单次调用超时是 45s（.env 的 LLM_TIMEOUT），前端必须比它更宽 —— 取 60s。
 */
export const REQUEST_TIMEOUT = 60000

/** 本地缓存键（统一前缀，便于「清空本地身份」一次清干净） */
export const STORAGE_KEYS = {
	userId: 'lightstep_user',
	settings: 'lightstep_settings',
	baseUrl: 'lightstep_baseurl'
}
