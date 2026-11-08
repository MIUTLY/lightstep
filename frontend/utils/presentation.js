/**
 * 表现素材（桌宠 / 票根）的统一读取层。
 *
 * 2026-11-08 后端 main@b8e6e026 起，每项任务有自己的「表现计步」：
 *   items[].presentation / focus.presentation / TaskView.presentation / receipt 事件 presentation
 * 结构都一样（见 docs/task-presentation-assets.md）：
 *
 *   {
 *     available: true,
 *     completed_steps: 1, step_number: 2,
 *     normal_stage: 'initial',                      // initial / starting / flow / reward
 *     normal_pet: { url, width, height },           // 当前该显示的桌宠
 *     receipt: { id:'1.2', url, preview:{url}, composition:{…} },
 *     source: 'recorded' | 'operation_history' | 'legacy_count_unavailable',
 *     asset_version: '2026-11-08-v1'
 *   }
 *
 * 规则（后端文档明确要求，前端不能自己发明）：
 *   - 不许用叶子数 / steps_done / 走神形象去重算票根；只认后端下发的 receipt。
 *   - available=false 时用中性缺图，不随机挑票根、不声称精确步号。
 *   - 素材 url 是「含 /api 的绝对路径」，用 api.assetUrl() 拼 origin。
 *   - 素材一年不可变缓存；客户端不要一次加载全部大图（票根按需取）。
 */
import { assetUrl, assetsManifest } from '@/api/index.js'

/** 默认空闲超时（后端 policy 没下来时的兜底，和后端默认值一致） */
export const DEFAULT_IDLE_SECONDS = 300

let manifestPromise = null

/** 取素材清单（进程内缓存；失败后允许下次重试） */
export function loadManifest(force = false) {
	if (force) manifestPromise = null
	if (!manifestPromise) {
		manifestPromise = assetsManifest()
			.then((data) => (data && typeof data === 'object' ? data : null))
			.catch(() => {
				manifestPromise = null
				return null
			})
	}
	return manifestPromise
}

/** 桌宠图片地址（已是可直接放进 <image src> 的绝对地址）；没有就返回空串 */
export function petImageUrl(presentation) {
	const pet = presentation && presentation.normal_pet
	if (!pet || !pet.url) return ''
	return assetUrl(pet.url)
}

/** 桌宠宽高比（width / height），拿不到时按 1:1 处理，避免容器抖动 */
export function petRatio(presentation) {
	const pet = presentation && presentation.normal_pet
	const w = pet && Number(pet.width)
	const h = pet && Number(pet.height)
	if (!w || !h) return 1
	return w / h
}

/** 走神图地址：优先用清单里 idle_policy.idle_pet，其次清单 pets.distracted */
export function idlePetUrl(manifest) {
	if (!manifest) return ''
	const policyPet = manifest.idle_policy && manifest.idle_policy.idle_pet
	if (policyPet && policyPet.url) return assetUrl(policyPet.url)
	const distracted = manifest.pets && manifest.pets.distracted
	return distracted && distracted.url ? assetUrl(distracted.url) : ''
}

/** 空闲超时秒数：优先用后端 policy，其次清单 idle_policy，最后 300 */
export function idleTimeoutSeconds(policy, manifest) {
	const fromPolicy = policy && Number(policy.idle_timeout_seconds)
	if (fromPolicy > 0) return fromPolicy
	const fromManifest = manifest && manifest.idle_policy && Number(manifest.idle_policy.timeout_seconds)
	return fromManifest > 0 ? fromManifest : DEFAULT_IDLE_SECONDS
}

/**
 * 后端下发的票根（当前这一页该印哪张）。
 * @returns {{id:string,url:string,previewUrl:string,composition:Object}|null}
 */
export function receiptArt(presentation) {
	const receipt = presentation && presentation.receipt
	if (!receipt || !receipt.url) return null
	return {
		id: receipt.id || '',
		url: assetUrl(receipt.url),
		previewUrl: receipt.preview && receipt.preview.url ? assetUrl(receipt.preview.url) : assetUrl(receipt.url),
		composition: receipt.composition || null
	}
}

/** 表现是否可用（数据缺失时后端会让它 false） */
export function presentationAvailable(presentation) {
	return !!(presentation && presentation.available)
}

/** 从事件数组里找最后一条 receipt 事件（含 occurred_date 与 presentation） */
export function lastReceiptEvent(events) {
	const list = Array.isArray(events) ? events : []
	for (let i = list.length - 1; i >= 0; i -= 1) {
		if (list[i] && list[i].kind === 'receipt') return list[i]
	}
	return null
}

/**
 * 下载一张网络素材到本地临时文件（canvas 的 drawImage 只吃本地路径）。
 * 失败返回空串，由调用方降级——不能因为图挂了就禁用完成/退出。
 */
export function downloadAsset(url) {
	if (!url) return Promise.resolve('')
	return new Promise((resolve) => {
		uni.downloadFile({
			url,
			success: (res) => resolve(res.statusCode === 200 ? res.tempFilePath : ''),
			fail: () => resolve('')
		})
	})
}
