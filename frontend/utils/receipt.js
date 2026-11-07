/**
 * 把「今日回执」画到 canvas 再存相册。
 *
 * 为什么要重画一遍：小程序不能直接把页面 DOM 截成图片，
 * 所以屏幕上用 ReceiptCard.vue（CSS 版），存相册时用 canvas 画一份同样排版的图。
 * 两边比例、文案、颜色保持一致（600×900，即竖版 2:3）。
 *
 * 用的是 uni-app 的**旧版 canvas API**（canvas-id + uni.createCanvasContext），
 * 因为它在 mp-weixin / H5 / App 上都可用；旧 API 没有 ellipse / setLineDash，
 * 所以椭圆用四段贝塞尔、虚线按段手绘。
 */
import { catPoseOfSteps } from './format.js'

/** 画布设计尺寸（px），与页面上的 520×780rpx 同比 */
export const RECEIPT_W = 600
export const RECEIPT_H = 900

const COLORS = {
	bg: '#f5f0e8',
	paper: '#fbf8f2',
	ink: '#2c2824',
	inkSoft: '#5a544c',
	muted: '#958c80',
	line: '#e8e0d2',
	cat: '#211c16',
	amber: '#d9872b'
}

const SENSORY_COLORS = {
	bg: '#ffffff',
	paper: '#fafafa',
	ink: '#1a1a1a',
	inkSoft: '#3d3d3d',
	muted: '#8a8a8a',
	line: '#dcdcdc',
	cat: '#111111',
	amber: '#555555'
}

const K = 0.5522847498

/** 用四段贝塞尔画椭圆路径（旧 canvas API 没有 ellipse） */
function ellipsePath(ctx, cx, cy, rx, ry) {
	const ox = rx * K
	const oy = ry * K
	ctx.beginPath()
	ctx.moveTo(cx, cy - ry)
	ctx.bezierCurveTo(cx + ox, cy - ry, cx + rx, cy - oy, cx + rx, cy)
	ctx.bezierCurveTo(cx + rx, cy + oy, cx + ox, cy + ry, cx, cy + ry)
	ctx.bezierCurveTo(cx - ox, cy + ry, cx - rx, cy + oy, cx - rx, cy)
	ctx.bezierCurveTo(cx - rx, cy - oy, cx - ox, cy - ry, cx, cy - ry)
	ctx.closePath()
}

function roundRectPath(ctx, x, y, w, h, r) {
	ctx.beginPath()
	ctx.moveTo(x + r, y)
	ctx.lineTo(x + w - r, y)
	ctx.arc(x + w - r, y + r, r, -Math.PI / 2, 0)
	ctx.lineTo(x + w, y + h - r)
	ctx.arc(x + w - r, y + h - r, r, 0, Math.PI / 2)
	ctx.lineTo(x + r, y + h)
	ctx.arc(x + r, y + h - r, r, Math.PI / 2, Math.PI)
	ctx.lineTo(x, y + r)
	ctx.arc(x + r, y + r, r, Math.PI, Math.PI * 1.5)
	ctx.closePath()
}

/** 虚线：按段手绘 */
function dashedLine(ctx, x1, x2, y, color) {
	const dash = 14
	const gap = 10
	ctx.setStrokeStyle(color)
	ctx.setLineWidth(1)
	let x = x1
	while (x < x2) {
		ctx.beginPath()
		ctx.moveTo(x, y)
		ctx.lineTo(Math.min(x + dash, x2), y)
		ctx.stroke()
		x += dash + gap
	}
}

/** 小步美术资源的宽高比（static/xiaobu.png = 400×238） */
const CAT_RATIO = 238 / 400

/**
 * 画小步。
 *
 * 现在用真实美术资源（static/xiaobu.png），屏幕上的 <CatBuddy> 和票根上这张图是同一张，
 * 所以回执里的猫和界面里长得完全一样。
 *
 * 为什么要把路径传进来：旧版 canvas 的 drawImage 在部分环境里不认包内路径，
 * 需要先用 uni.getImageInfo 拿到真实路径（由页面负责解析），这里只负责画。
 *
 * @param {string} [imagePath] 解析后的图片路径；为空时退化成一个圆润剪影，不至于缺一块
 */
function drawCat(ctx, cx, cy, pose, c, imagePath) {
	const w = 230
	const h = w * CAT_RATIO

	if (imagePath) {
		try {
			ctx.drawImage(imagePath, cx - w / 2, cy - h / 2, w, h)
			return
		} catch (e) {
			/* 落到下面的剪影兜底 */
		}
	}

	ctx.setFillStyle(c.cat)
	ellipsePath(ctx, cx, cy, w * 0.45, h * 0.36)
	ctx.fill()
}

/**
 * 在 canvas 上下文上画一张回执。
 * @param {Object} ctx   uni.createCanvasContext 拿到的上下文
 * @param {Object} options
 * @param {number} [options.steps]    今日步数（决定小步姿势）
 * @param {string} [options.line]     用户写的那句话
 * @param {string} [options.date]     右下角日期，例如 2026.11.07
 * @param {boolean} [options.sensory] 感官友好模式（纯黑白）
 * @param {string} [options.catImagePath] 小步图片的真实路径（由页面用 uni.getImageInfo 解析）
 * @param {Function} [done]           ctx.draw 完成后的回调
 */
export function drawReceipt(ctx, options, done) {
	const opts = options || {}
	const c = opts.sensory ? SENSORY_COLORS : COLORS
	const pose = catPoseOfSteps(opts.steps)
	const centerX = RECEIPT_W / 2

	// 底色
	ctx.setFillStyle(c.bg)
	ctx.fillRect(0, 0, RECEIPT_W, RECEIPT_H)

	// 纸面
	const px = 40
	const py = 30
	const pw = RECEIPT_W - 80
	const ph = RECEIPT_H - 60
	ctx.setFillStyle(c.paper)
	roundRectPath(ctx, px, py, pw, ph, 14)
	ctx.fill()
	ctx.setStrokeStyle(c.line)
	ctx.setLineWidth(1)
	roundRectPath(ctx, px, py, pw, ph, 14)
	ctx.stroke()

	// 票根齿孔（用底色挖半圆）
	ctx.setFillStyle(c.bg)
	;[px, px + pw].forEach((x) => {
		ctx.beginPath()
		ctx.arc(x, py + ph / 2, 26, 0, Math.PI * 2)
		ctx.fill()
	})

	// 页眉
	ctx.setFillStyle(c.muted)
	ctx.setFontSize(18)
	ctx.setTextAlign('center')
	ctx.fillText('轻 步 · 今 日 回 执', centerX, 108)

	// 小步
	drawCat(ctx, centerX, 296, pose, c, opts.catImagePath)

	// 大字
	ctx.setFillStyle(c.ink)
	ctx.setFontSize(44)
	ctx.fillText('今天到此为止', centerX, 500)

	// 虚线
	dashedLine(ctx, 120, RECEIPT_W - 120, 552, c.line)

	// 提示
	ctx.setFillStyle(c.muted)
	ctx.setFontSize(18)
	ctx.fillText('写给自己的一句话', centerX, 596)

	// 三条横线
	const lineX1 = 120
	const lineX2 = RECEIPT_W - 120
	;[660, 712, 764].forEach((y) => {
		ctx.beginPath()
		ctx.setStrokeStyle(c.line)
		ctx.setLineWidth(1)
		ctx.moveTo(lineX1, y)
		ctx.lineTo(lineX2, y)
		ctx.stroke()
	})

	// 用户写的那一句（放在第一条横线上方）
	const written = String(opts.line || '').trim()
	if (written) {
		ctx.setFillStyle(c.inkSoft)
		ctx.setFontSize(24)
		ctx.fillText(written.slice(0, 18), centerX, 648)
	}

	// 日期
	ctx.setFillStyle(c.muted)
	ctx.setFontSize(16)
	ctx.setTextAlign('right')
	ctx.fillText(opts.date || '', RECEIPT_W - 90, 830)
	ctx.setTextAlign('left')

	ctx.draw(false, () => {
		if (typeof done === 'function') done()
	})
}

/**
 * 把画好的 canvas 存进相册（含授权被拒的引导）。
 * @param {string} canvasId 页面里 <canvas canvas-id="..."> 的 id
 * @param {Object} instance 组件实例（getCurrentInstance().proxy）
 */
export function saveCanvasToAlbum(canvasId, instance) {
	return new Promise((resolve, reject) => {
		uni.canvasToTempFilePath(
			{
				canvasId,
				destWidth: RECEIPT_W,
				destHeight: RECEIPT_H,
				success: (res) => {
					uni.saveImageToPhotosAlbum({
						filePath: res.tempFilePath,
						success: () => resolve(true),
						fail: (err) => {
							const msg = (err && err.errMsg) || ''
							if (msg.indexOf('auth deny') >= 0 || msg.indexOf('authorize') >= 0) {
								uni.showModal({
									title: '需要相册权限',
									content: '允许保存后，回执就只存在你自己的相册里。',
									confirmText: '去设置',
									cancelText: '算了',
									success: (r) => {
										if (r.confirm) uni.openSetting({})
										reject(new Error('已取消保存'))
									}
								})
								return
							}
							reject(new Error(msg || '保存失败'))
						}
					})
				},
				fail: (err) => reject(new Error((err && err.errMsg) || '导出图片失败'))
			},
			instance
		)
	})
}
