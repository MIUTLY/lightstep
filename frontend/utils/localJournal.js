/**
 * 私人静默手帐 · 本地存储（不经过后端）
 *
 * 为什么改本地：
 *   仓库后端已把 /api/journal、/api/journal/add、DELETE /api/journal/{id} 全部
 *   改成 410 detail.code=JOURNAL_CLIENT_ONLY，并在 docs/api.md 里写明
 *   「回执图片和私人留言仅在客户端保存，不恢复服务端 journal 写入或自动生成」。
 *   所以手帐的增删查全部在 uni storage 里做，一条都不上云。
 *
 * 存储结构（一个 key 存数组，最新的在前）：
 *   [
 *     {
 *       id: 'l_xxx',              // 本地自增 id
 *       date: '2026-11-07',       // 清单归属日
 *       occurred_date: '2026-11-07', // 实际结束日（2026-11-08 后端 receipt 事件新增，跨天时与 date 不同）
 *       steps_done: 3,            // 这张回执对应的今日步数
 *       titles: ['写论文'],        // 当天做过的任务
 *       note: '今天其实有点累',     // 用户手写的一句话，可为空
 *       created_at: '2026-11-07T15:02:11',
 *       imagePath: 'wxfile://...' // 本地持久图片路径，可能为空（没保存图片时）
 *     }
 *   ]
 */
import { todayCN } from '@/utils/format.js'

const STORAGE_KEY = 'lightstep_local_journal'
/** 手帐最多保留多少条（防止无限膨胀；产品不统计，所以不做提示） */
const MAX_ENTRIES = 500

function readAll() {
	try {
		const raw = uni.getStorageSync(STORAGE_KEY)
		if (!raw) return []
		const list = typeof raw === 'string' ? JSON.parse(raw) : raw
		return Array.isArray(list) ? list : []
	} catch (e) {
		return []
	}
}

function writeAll(list) {
	try {
		uni.setStorageSync(STORAGE_KEY, JSON.stringify(list))
		return true
	} catch (e) {
		return false
	}
}

function nextId() {
	return 'l_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6)
}

/** 列表（最新在前） */
export function listEntries() {
	return readAll()
}

/**
 * 新增一条手帐。写入成功返回这条记录，**写失败返回 null**。
 *
 * ⚠️ 2026-11-08 后端协议（docs/task-presentation-assets.md）要求：
 *   保存失败不能提示成功；同日多页要追加、不能用 date 当唯一页键覆盖旧页。
 *   所以这里必须把 writeAll 的结果返回给调用方，不能假装存好了。
 *
 * @param {Object} entry { steps_done, titles, note, imagePath, date, occurred_date }
 */
export function addEntry(entry = {}) {
	const occurred = String(entry.occurred_date || '').trim()
	const record = {
		id: nextId(),
		// date 仍是「清单归属日」，occurred_date 是实际结束日（跨天时两者不同）
		date: entry.date || (occurred ? occurred : todayCN().replace(/\./g, '-')),
		occurred_date: occurred || entry.date || todayCN().replace(/\./g, '-'),
		steps_done: Number(entry.steps_done) || 0,
		titles: Array.isArray(entry.titles) ? entry.titles : [],
		note: String(entry.note || '').trim(),
		created_at: new Date().toISOString().slice(0, 19),
		imagePath: entry.imagePath || ''
	}
	const list = readAll()
	list.unshift(record)
	if (!writeAll(list.slice(0, MAX_ENTRIES))) return null
	return record
}

/** 删除一条（删了就是删了，不问理由） */
export function removeEntry(id) {
	const list = readAll()
	const next = list.filter((x) => x.id !== id)
	if (next.length === list.length) return false
	return writeAll(next)
}

/** 清空（设置页「换一个人」时用） */
export function clearEntries() {
	return writeAll([])
}

/**
 * 把临时图片保存成**持久**文件。
 *
 * 为什么要这一步：canvasToTempFilePath 出来的是临时文件，
 * 小程序重启后会失效，手帐里存的图就成了空图。
 * 优先用 FileSystemManager.saveFile（新版），失败再用 uni.saveFile（旧版）。
 *
 * @param {string} tempFilePath 临时文件路径
 * @returns {Promise<string>} 持久路径；失败返回空串（调用方降级为「只存文字」）
 */
export function persistImage(tempFilePath) {
	if (!tempFilePath) return Promise.resolve('')
	return new Promise((resolve) => {
		try {
			const fs = uni.getFileSystemManager && uni.getFileSystemManager()
			if (fs && typeof fs.saveFile === 'function') {
				fs.saveFile({
					tempFilePath,
					success: (res) => resolve(res.savedFilePath || ''),
					fail: () => resolve('')
				})
				return
			}
		} catch (e) {
			/* 落到下面的旧 API */
		}
		if (typeof uni.saveFile === 'function') {
			uni.saveFile({
				tempFilePath,
				success: (res) => resolve(res.savedFilePath || ''),
				fail: () => resolve('')
			})
			return
		}
		resolve('')
	})
}
