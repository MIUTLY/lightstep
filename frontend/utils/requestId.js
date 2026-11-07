/**
 * 幂等用的 request_id 生成器
 *
 * 后端新主流程（今日备忘录）要求每个写操作带一个**客户端生成、全局唯一**的 request_id：
 *   - 每次新操作 → 新 ID
 *   - 同一次操作的网络重试 → 必须复用同一个 ID（否则会重复推进进度/重复产生事件）
 *
 * 小程序里没有 crypto.randomUUID（基础库不保证），这里用「时间戳 + 随机 + 自增」拼，
 * 足够唯一且不依赖任何库。
 */
let seq = 0

export function newRequestId() {
	seq += 1
	const t = Date.now().toString(36)
	const r = Math.random().toString(36).slice(2, 10)
	return 'rq_' + t + '_' + r + '_' + seq
}

/**
 * 带重试的单次操作 ID。
 * 用法：把 id 存在调用处，重试时**传同一个 id**，不要重新生成。
 */
export function withRetryId(fn) {
	const id = newRequestId()
	return () => fn(id)
}
