<template>
	<view class="page-root" :class="themeClass" @touchstart="onUserTouch">
		<!-- 背景：设计稿的木地板 + 奶白墙（上半墙面、下半地板） -->
		<image class="bg" src="/static/focus-bg.jpg" mode="aspectFill" />

		<view class="page-safe" :style="statusBarStyle"></view>

		<!-- 左上角：喇叭图标（设计稿原样，56×56） -->
		<view class="sound-btn" hover-class="sound-hover" @tap.stop="onSound">
			<view class="spk">
				<view class="spk-box"></view>
				<view class="spk-cone"></view>
				<view class="spk-wave spk-wave-1"></view>
				<view class="spk-wave spk-wave-2"></view>
			</view>
		</view>

		<!-- 墙面区：任务名 + 三个竖向按钮 -->
		<view class="wall">
			<text class="task-title">{{ taskTitle }}</text>

			<view v-if="currentStep" class="task-step">
				<text>{{ currentStep }}</text>
			</view>

			<view v-if="pendingQuestion" class="clarify-card">
				<text class="clarify-text">{{ pendingQuestion }}</text>
				<text class="clarify-hint">点左侧便签或右下角小布，把范围告诉它。</text>
			</view>

			<!-- 设计稿顺序：完成了(宽) / 重一点 / 轻一点 -->
			<view class="pills">
				<view class="pill pill-done" :class="{ disabled: today.busy || !hasFocus }" hover-class="pill-hover" @tap.stop="onDone">
					<text class="pill-text pill-text-done">完成了</text>
				</view>
				<view class="pill pill-slim" :class="{ disabled: today.busy || !hasFocus }" hover-class="pill-hover" @tap.stop="onHeavier">
					<text class="pill-text">重一点</text>
				</view>
				<view class="pill pill-slim" :class="{ disabled: today.busy || !hasFocus }" hover-class="pill-hover" @tap.stop="onLighter">
					<text class="pill-text">轻一点</text>
				</view>
			</view>
		</view>

		<!-- 左侧中部：粉色便签按钮（点它打开「思绪倾倒」）
		     澄清态下先让位给问题卡片，避免和小步的提问叠在一起 -->
		<view v-if="!pendingQuestion" class="note-btn" hover-class="note-hover" @tap.stop="openThoughts">
			<image class="note-img" src="/static/focus-book-1.png" mode="widthFix" />
		</view>

		<!-- 右下角：站在地板上的小猫（它本身就是小布聊天入口） -->
		<view class="floor-cat" hover-class="cat-hover" @tap.stop="toggleChat">
			<image class="floor-cat-img" src="/static/focus-book-2.png" mode="widthFix" />
		</view>

		<!-- 底部：就到这儿吧 -->
		<view class="bottom">
			<view class="pill pill-exit" hover-class="pill-hover" @tap.stop="onExit">
				<text class="pill-text pill-text-exit">{{ exiting ? '正在收尾…' : '就到这儿吧' }}</text>
			</view>
		</view>

		<!-- 右下角小布（就是上面那只猫） -->

		<!-- ================= 思绪倾倒（点便签打开） ================= -->
		<view v-if="thoughtOpen" class="thought-mask" @tap.stop="closeThoughts">
			<view class="thought-card" @tap.stop="noop">
				<image class="thought-badge" src="/static/focus-book-1.png" mode="widthFix" />
				<text class="thought-title">思绪倾倒</text>

				<view class="thought-field">
					<textarea
						class="thought-textarea"
						v-model="thoughtText"
						placeholder="在此输入您的想法、创意或笔记……"
						placeholder-class="thought-ph"
						:maxlength="500"
						:focus="thoughtOpen"
					/>
					<view class="thought-lines">
						<view class="thought-line"></view>
						<view class="thought-line"></view>
						<view class="thought-line"></view>
					</view>
				</view>

				<view class="thought-save" hover-class="thought-save-hover" @tap.stop="saveThought">
					<text class="thought-save-text">保存想法</text>
				</view>
			</view>
		</view>

		<!-- ================= 小布聊天框 ================= -->
		<view v-if="chatOpen" class="chat-mask" @tap.stop="closeChat">
			<view class="chat-panel" @tap.stop="noop">
				<view class="chat-head">
					<text class="chat-title">跟小布说</text>
					<text class="chat-close" @tap.stop="closeChat">收起</text>
				</view>

				<scroll-view class="chat-list" scroll-y :scroll-into-view="chatAnchor">
					<view v-for="m in chatMessages" :key="m.id" class="msg" :class="m.role">
						<text class="msg-text">{{ m.text }}</text>
					</view>
					<view id="chat-bottom" class="chat-anchor"></view>
				</scroll-view>

				<view class="chat-input-row">
					<input
						class="chat-input"
						v-model="draft"
						:focus="chatOpen"
						placeholder="加一件，或者补充范围…"
						confirm-type="send"
						@confirm="sendChat"
					/>
					<view class="send-btn" :class="{ disabled: today.busy || !draft.trim() }" @tap.stop="sendChat">
						<text>↑</text>
					</view>
				</view>
			</view>
		</view>

		<!-- 离屏 canvas：生成回执图用 -->
		<canvas canvas-id="focusReceipt" :style="canvasStyle" />

		<SoftLine :text="recallText" />
	</view>
</template>

<script setup>
/**
 * 专注模式（按 Figma 设计稿还原）
 *
 * 设计稿版式（fileKey a4LwTwEh3akDn7IkZygSh7 / node 0:1）：
 *   ┌─────────────────────────────┐
 *   │ [喇叭图标]                    │  ← 左上角 56×56
 *   │                                │
 *   │          打开单词书            │  ← 任务名 55px #5E5D62
 *   │        [  完成了  ]            │  ← 400×70
 *   │        [ 重一点 ]              │  ← 290×48
 *   │  [便签] [ 轻一点 ]             │  ← 290×48；便签在左侧中部，点它开思绪倾倒
 *   │                                │
 *   │              🐱(蹲在地板上)     │  ← 右下角
 *   │        [ 就到这儿吧 ]          │  ← 290×50
 *   └─────────────────────────────┘
 *
 * 按钮规格：白底 rgba(255,255,255,.84)、边框 #F9E1C4 2px、圆角 47.5px、
 *          外发光 0 0 14.9px rgba(254,214,108,.6) + 内发光 inset 0 0 27.1px rgba(255,238,192,1)，
 *          文字 #5E5D62（就到这儿吧 #333333）。768px 设计宽 ≈ 750rpx。
 *
 * 交互：便签 → 思绪倾倒卡片；小布 → 聊天框（新增任务）；
 *      就到这儿吧 → 结束本轮 + 生成回执图 + 存进本地手账。
 */
import { computed, getCurrentInstance, nextTick, ref } from 'vue'
import { onHide, onShow } from '@dcloudio/uni-app'

import SoftLine from '@/components/SoftLine.vue'
import { useSettings } from '@/store/settings.js'
import { useToday } from '@/store/today.js'
import { useSoftRecall } from '@/composables/useSoftRecall.js'
import { addEntry, persistImage } from '@/utils/localJournal.js'
import { todayCN } from '@/utils/format.js'
import { RECEIPT_H, RECEIPT_W, drawReceipt, exportCanvasTempPath } from '@/utils/receipt.js'
import { getStatusBarHeight } from '@/utils/systemInfo.js'

const settings = useSettings()
const today = useToday()
const instance = getCurrentInstance()

const themeClass = computed(() => (settings.sensory ? 'theme-sensory' : ''))
const statusBarStyle = 'height:' + getStatusBarHeight() + 'px;'
const canvasStyle = 'position:fixed;left:-2000px;top:0;width:' + RECEIPT_W + 'px;height:' + RECEIPT_H + 'px;'

/* ---------------- 任务内容 ---------------- */

const hasFocus = computed(() => today.hasFocus())

/**
 * 待澄清的问题（PR #16 起后端会同时在列表里下发 clarifications）：
 *   - 备忘录点进来时 pendingSelect 带着问题
 *   - 也可能是别的任务还没澄清（can_enter_focus=false）
 */
const pendingQuestion = computed(() => {
	if (hasFocus.value) return ''
	if (today.pendingSelect && today.pendingSelect.question) return today.pendingSelect.question
	const first = today.firstClarification()
	return first ? first.question : ''
})

const taskTitle = computed(() => {
	if (today.focus && today.focus.title) return today.focus.title
	if (today.pendingSelect) {
		const item = today.items.find((x) => x.id === today.pendingSelect.itemId)
		if (item) return item.title
	}
	return '打开单词书'
})

const currentStep = computed(() => {
	const f = today.focus
	return f && f.step ? f.step.current_step || '' : ''
})

const doneCount = computed(() => today.completedActions().length)

/* ---------------- 进页面自动开一项 ---------------- */

onShow(async () => {
	settings.load()
	resumeRecall()
	if (!today.loaded) await today.load()
	if (today.hasFocus() || today.pendingSelect) return
	// 还有没澄清完的任务时不要抢着开专注（后端 can_enter_focus=false）
	if (today.canEnterFocus === false || today.hasClarifications()) return

	const id = today.suggestedItemId || (today.items[0] && today.items[0].id)
	if (!id) return
	const view = await today.select(id)
	if (!view) return
	const status = view.operation && view.operation.status
	if (status === 'needs_clarification') {
		const first = today.firstClarification()
		today.pendingSelect = { itemId: id, question: (first && first.question) || view.reply || '还需要补充一点信息' }
	} else if (status === 'failed') {
		uni.showToast({ title: (view.operation.error && view.operation.error.message) || '没能开始', icon: 'none' })
	}
})

onHide(() => {
	stopRecall()
})

/* ---------------- 喇叭（设计稿里左上角那个图标） ---------------- */

function onSound() {
	// 后端没有 TTS，也没有朗读接口；这里如实说明，不假装能播。
	uni.showToast({ title: '朗读还没接，先用眼睛看这一步', icon: 'none' })
}

/* ---------------- 三个按钮 ---------------- */

async function onDone() {
	if (today.busy || !hasFocus.value) return
	const stepId = today.focus && today.focus.step && today.focus.step.step_id
	await today.complete(stepId)
	await handleEvents()
	if (!today.hasFocus()) uni.showToast({ title: '这一项做完了', icon: 'none' })
}

async function onLighter() {
	if (today.busy || !hasFocus.value) return
	await today.resize('smaller')
}

async function onHeavier() {
	if (today.busy || !hasFocus.value) return
	await today.resize('bigger')
}

/* ---------------- 就到这儿吧 ---------------- */

const exiting = ref(false)

async function onExit() {
	if (exiting.value) return
	exiting.value = true
	const steps = doneCount.value
	const title = today.focus ? today.focus.title : ''

	try {
		if (today.hasFocus()) {
			await today.end()
			await handleEvents()
		}

		let imagePath = ''
		try {
			await renderReceipt(title, steps)
			const tempPath = await exportCanvasTempPath('focusReceipt', instance.proxy)
			imagePath = await persistImage(tempPath)
		} catch (e) {
			imagePath = ''
		}

		addEntry({ note: '', steps_done: steps, titles: title ? [title] : [], imagePath })
		uni.showToast({ title: imagePath ? '存进手账了' : '记下了（图没存上）', icon: 'none' })
	} finally {
		exiting.value = false
		backToMemo()
	}
}

function renderReceipt(title, steps) {
	return new Promise((resolve, reject) => {
		uni.getImageInfo({
			src: '/static/xiaobu.png',
			success: (info) => {
				nextTick(() => {
					const ctx = uni.createCanvasContext('focusReceipt', instance.proxy)
					drawReceipt(
						ctx,
						{
							steps: steps || 0,
							line: title ? '这次做到「' + title + '」' : '这次就到这儿。',
							date: todayCN(),
							sensory: settings.sensory,
							catImagePath: info.path || ''
						},
						resolve
					)
				})
			},
			fail: () => reject(new Error('拿不到小猫图'))
		})
	})
}

async function handleEvents() {
	for (const e of today.events || []) {
		if (!e || !e.id) continue
		if (today.isAcked(e.id)) continue
		await today.ack(e.id)
	}
}

/* ---------------- 思绪倾倒 ---------------- */

const THOUGHTS_KEY = 'lightstep_thoughts'
const thoughtOpen = ref(false)
const thoughtText = ref('')

function openThoughts() {
	thoughtOpen.value = true
}

function closeThoughts() {
	thoughtOpen.value = false
	thoughtText.value = ''
}

function saveThought() {
	const text = thoughtText.value.trim()
	if (!text) {
		uni.showToast({ title: '还没写呢', icon: 'none' })
		return
	}
	let list = []
	try {
		const raw = uni.getStorageSync(THOUGHTS_KEY)
		const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
		list = Array.isArray(parsed) ? parsed : []
	} catch (e) {
		list = []
	}
	list.unshift({
		id: 't_' + Date.now().toString(36),
		text,
		at: new Date().toISOString().slice(0, 19),
		task: today.focus ? today.focus.title : ''
	})
	try {
		uni.setStorageSync(THOUGHTS_KEY, JSON.stringify(list.slice(0, 200)))
		uni.showToast({ title: '想法存好了', icon: 'none' })
	} catch (e) {
		uni.showToast({ title: '没存下，再试一次', icon: 'none' })
	}
	closeThoughts()
}

/* ---------------- 小布聊天框 ---------------- */

const chatOpen = ref(false)
const draft = ref('')
const chatAnchor = ref('')
const chatMessages = ref([{ id: 'm0', role: 'cat', text: '想加一件，或者告诉我范围，我记下来。' }])

let msgSeq = 0
function pushMsg(role, text) {
	msgSeq += 1
	chatMessages.value.push({ id: 'm' + Date.now() + '_' + msgSeq, role, text })
	nextTick(() => {
		chatAnchor.value = ''
		nextTick(() => {
			chatAnchor.value = 'chat-bottom'
		})
	})
}

function toggleChat() {
	chatOpen.value = !chatOpen.value
}

function closeChat() {
	chatOpen.value = false
	draft.value = ''
}

function noop() {}

function looksLikeRemove(text) {
	return /删|移除|不要了|去掉/.test(text)
}

async function sendChat() {
	const text = draft.value.trim()
	if (!text || today.busy) return
	draft.value = ''
	pushMsg('user', text)

	if (looksLikeRemove(text)) {
		pushMsg('cat', '删掉清单里的一条我还做不到，你先留着，或者点「完成了」把它划掉。')
		return
	}

	// 专注中：只能新增任务（后端规定专注期间走 focus/capture，走 chat 会 409）
	if (today.hasFocus()) {
		const view = await today.capture(text)
		const status = view && view.operation && view.operation.status
		if (status === 'succeeded') {
			const n = (view.capture && view.capture.count) || 1
			pushMsg('cat', '好，加了 ' + n + ' 件，等手上这件做完就轮到它。')
			await today.load()
		} else if (status === 'needs_clarification') {
			pushMsg('cat', (view && view.reply) || '放在哪儿好？说个名字我就插进去。')
		} else {
			pushMsg('cat', (view && view.operation && view.operation.error && view.operation.error.message) || '没加上，再说一次试试。')
		}
		return
	}

	// 还没开始专注：统一走 /api/chat 的 chat 路由。
	// 后端自己判断这句话是「闲聊 / 回答某个待澄清问题 / 提出新任务」。
	// 但实测模型偶尔会把「写数学作业，第3章1到10题」这类回答误判成新任务，
	// 所以有待澄清项时，把「在回答哪一项」显式写进消息里（实测能稳定命中 answer）。
	const first = today.firstClarification()
	const outText = first ? '关于「' + first.title + '」：' + text : text
	const view = await today.chat(outText)
	if (!view) {
		pushMsg('cat', today.lastError || '没连上，再说一次试试。')
		return
	}
	const status = view.operation && view.operation.status
	const reply = (view.reply || '').trim()

	if (today.hasFocus()) {
		// 澄清答完、后端已经把专注开起来了
		today.pendingSelect = null
		pushMsg('cat', reply || '好，这就开始。')
		return
	}
	if (status === 'failed') {
		pushMsg('cat', (view.operation.error && view.operation.error.message) || '这次没弄好，再说一次试试。')
		return
	}
	// 还有待澄清的问题：把下一个问题摆给用户
	const next = today.firstClarification()
	if (next) {
		today.pendingSelect = { itemId: next.id, question: next.question }
		pushMsg('cat', reply && reply !== next.question ? reply : next.question)
		return
	}
	pushMsg('cat', reply || '嗯，记下了。')
}

/* ---------------- 召回 / 返回 ---------------- */

const {
	text: recallText,
	poke: pokeRecall,
	resume: resumeRecall,
	stop: stopRecall
} = useSoftRecall({ enabled: () => !settings.dnd })

function onUserTouch() {
	pokeRecall()
}

function backToMemo() {
	const pages = getCurrentPages()
	if (pages && pages.length > 1) uni.navigateBack({ delta: 1 })
	else uni.reLaunch({ url: '/pages/memo/memo' })
}
</script>

<style scoped>
.page-root {
	position: relative;
	display: flex;
	flex-direction: column;
	width: 100%;
	box-sizing: border-box;
	height: 100vh;
	overflow: hidden;
	background-color: #f6f0e6;
}

/* ---------- 背景 ---------- */

.bg {
	position: absolute;
	left: 0;
	top: 0;
	width: 100%;
	height: 100%;
	z-index: 0;
}

.page-safe,
.sound-btn,
.wall,
.note-btn,
.bottom {
	position: relative;
	z-index: 2;
}

/* ---------- 左上角喇叭 ---------- */

.sound-btn {
	position: absolute;
	left: 40rpx;
	top: 96rpx;
	z-index: 5;
	width: 96rpx;
	height: 96rpx;
	display: flex;
	align-items: center;
	justify-content: center;
}

.sound-hover {
	opacity: 0.7;
}

/* 喇叭：一个方块 + 一个三角 + 两道弧 */
.spk {
	position: relative;
	width: 56rpx;
	height: 56rpx;
}

.spk-box {
	position: absolute;
	left: 0;
	top: 19rpx;
	width: 16rpx;
	height: 18rpx;
	border: 3rpx solid #5e5d62;
	border-right: none;
	border-radius: 4rpx 0 0 4rpx;
	box-sizing: border-box;
}

.spk-cone {
	position: absolute;
	left: 13rpx;
	top: 13rpx;
	width: 0;
	height: 0;
	border-top: 15rpx solid transparent;
	border-bottom: 15rpx solid transparent;
	border-right: 18rpx solid #5e5d62;
}

.spk-wave {
	position: absolute;
	border: 3rpx solid #5e5d62;
	border-radius: 50%;
	border-left-color: transparent;
	border-top-color: transparent;
	border-bottom-color: transparent;
	box-sizing: border-box;
}

.spk-wave-1 {
	left: 32rpx;
	top: 20rpx;
	width: 12rpx;
	height: 16rpx;
	border-radius: 0 50% 50% 0;
}

.spk-wave-2 {
	left: 32rpx;
	top: 13rpx;
	width: 18rpx;
	height: 30rpx;
	border-radius: 0 50% 50% 0;
}

/* ---------- 墙面内容 ---------- */

.wall {
	position: absolute;
	left: 0;
	right: 0;
	top: 230rpx;
	z-index: 3;
	display: flex;
	flex-direction: column;
	align-items: center;
}

/* 任务名：设计稿 55px → 54rpx */
.task-title {
	font-size: 54rpx;
	line-height: 1.3;
	text-align: center;
	color: #5e5d62;
	letter-spacing: 2rpx;
}

.task-step {
	margin-top: 14rpx;
	max-width: 560rpx;
	padding: 0 10rpx;
}

.task-step text {
	font-size: 24rpx;
	line-height: 1.6;
	text-align: center;
	color: #8b8891;
}

.clarify-card {
	margin-top: 20rpx;
	width: 520rpx;
	padding: 18rpx 22rpx;
	border-radius: 20rpx;
	background-color: rgba(255, 255, 255, 0.9);
	border: 2rpx solid #f9e1c4;
}

.clarify-text {
	display: block;
	font-size: 24rpx;
	line-height: 1.6;
	color: #5e5d62;
	text-align: center;
}

.clarify-hint {
	display: block;
	margin-top: 8rpx;
	font-size: 20rpx;
	color: #8b8891;
	text-align: center;
}

/* ---------- 竖向三个胶囊 ---------- */

.pills {
	margin-top: 44rpx;
	display: flex;
	flex-direction: column;
	align-items: center;
}

.pill {
	box-sizing: border-box;
	display: flex;
	align-items: center;
	justify-content: center;
	background-color: rgba(255, 255, 255, 0.84);
	border: 2rpx solid #f9e1c4;
	border-radius: 46rpx;
	box-shadow: 0 0 15rpx rgba(254, 214, 108, 0.6), inset 0 0 26rpx rgba(255, 238, 192, 1);
}

/* 完成了：400×70 → 391×68 */
.pill-done {
	width: 391rpx;
	height: 68rpx;
}

/* 重一点 / 轻一点：290×48 → 283×47，间距按设计稿 */
.pill-slim {
	width: 283rpx;
	height: 47rpx;
	margin-top: 24rpx;
}

.pill-hover {
	background-color: rgba(255, 255, 255, 0.96);
}

.pill.disabled {
	opacity: 0.55;
}

.pill-text {
	font-size: 29rpx;
	color: #5e5d62;
}

.pill-text-done {
	font-size: 35rpx;
}

/* ---------- 左侧中部：粉色便签（点开思绪倾倒） ---------- */

.note-btn {
	position: absolute;
	left: 92rpx;
	top: 720rpx;
	z-index: 4;
	width: 96rpx;
}

.note-hover {
	opacity: 0.82;
}

.note-img {
	display: block;
	width: 100%;
	height: auto;
}

/* ---------- 右下角：站在地板上的小猫（点它开口聊天） ---------- */

.floor-cat {
	position: absolute;
	right: 16rpx;
	bottom: 200rpx;
	z-index: 6;
	width: 400rpx;
}

.cat-hover {
	opacity: 0.86;
}

.floor-cat-img {
	display: block;
	width: 100%;
	height: auto;
}

/* ---------- 底部：就到这儿吧 ---------- */

.bottom {
	position: absolute;
	left: 0;
	right: 0;
	bottom: calc(70rpx + env(safe-area-inset-bottom));
	z-index: 5;
	display: flex;
	justify-content: center;
}

/* 290×50 → 283×49 */
.pill-exit {
	width: 283rpx;
	height: 49rpx;
}

.pill-text-exit {
	font-size: 31rpx;
	color: #333333;
}

/* ---------- 思绪倾倒卡片 ---------- */

.thought-mask {
	position: fixed;
	left: 0;
	right: 0;
	top: 0;
	bottom: 0;
	z-index: 70;
	background-color: rgba(60, 55, 45, 0.34);
	display: flex;
	align-items: center;
	justify-content: center;
}

.thought-card {
	position: relative;
	width: 600rpx;
	box-sizing: border-box;
	padding: 70rpx 40rpx 40rpx;
	border-radius: 26rpx;
	background-color: #fdf7e4;
	box-shadow: 0 18rpx 48rpx rgba(90, 76, 50, 0.24);
}

.thought-badge {
	position: absolute;
	left: 50%;
	top: -58rpx;
	width: 116rpx;
	margin-left: -58rpx;
	height: auto;
}

.thought-title {
	display: block;
	text-align: center;
	font-size: 40rpx;
	font-weight: 600;
	letter-spacing: 2rpx;
	color: #2f2f2f;
}

.thought-field {
	position: relative;
	margin-top: 26rpx;
	height: 280rpx;
	border-radius: 14rpx;
	border: 2rpx solid #c9c9c9;
	background-color: #ffffff;
	overflow: hidden;
}

.thought-textarea {
	position: relative;
	z-index: 2;
	width: 100%;
	height: 100%;
	box-sizing: border-box;
	padding: 18rpx 22rpx;
	font-size: 26rpx;
	line-height: 60rpx;
	color: #444444;
	background-color: transparent;
}

.thought-ph {
	color: #a8a8a8;
}

.thought-lines {
	position: absolute;
	left: 22rpx;
	right: 22rpx;
	top: 78rpx;
	z-index: 1;
}

.thought-line {
	height: 2rpx;
	margin-bottom: 58rpx;
	background-color: #e2e2e2;
}

.thought-save {
	margin-top: 30rpx;
	height: 88rpx;
	border-radius: 44rpx;
	background-color: #f0716b;
	display: flex;
	align-items: center;
	justify-content: center;
	box-shadow: 0 8rpx 20rpx rgba(240, 113, 107, 0.28);
}

.thought-save-hover {
	background-color: #e6605a;
}

.thought-save-text {
	font-size: 32rpx;
	color: #ffffff;
}

/* ---------- 聊天框 ---------- */

.chat-mask {
	position: fixed;
	left: 0;
	right: 0;
	top: 0;
	bottom: 0;
	z-index: 60;
	background-color: rgba(33, 28, 22, 0.2);
	display: flex;
	align-items: flex-end;
}

.chat-panel {
	width: 100%;
	box-sizing: border-box;
	padding: 24rpx 24rpx calc(24rpx + env(safe-area-inset-bottom));
	background-color: var(--surface);
	border-radius: 28rpx 28rpx 0 0;
}

.chat-head {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding-bottom: 12rpx;
}

.chat-title {
	font-size: 26rpx;
	font-weight: 600;
	color: var(--ink);
}

.chat-close {
	font-size: 22rpx;
	color: var(--muted);
}

.chat-list {
	max-height: 420rpx;
}

.chat-anchor {
	height: 2rpx;
}

.msg {
	display: flex;
	margin-top: 12rpx;
}

.msg.user {
	justify-content: flex-end;
}

.msg-text {
	max-width: 84%;
	padding: 14rpx 20rpx;
	border-radius: 18rpx;
	font-size: 26rpx;
	line-height: 1.6;
	background-color: var(--surface-soft);
	color: var(--ink);
}

.msg.user .msg-text {
	background-color: var(--cat);
	color: #fdfaf5;
}

.chat-input-row {
	display: flex;
	align-items: center;
	margin-top: 16rpx;
}

.chat-input {
	flex: 1;
	height: 80rpx;
	padding: 0 20rpx;
	border-radius: 18rpx;
	border: 1rpx solid var(--line);
	background-color: var(--surface-soft);
	color: var(--ink);
	font-size: 26rpx;
}

.send-btn {
	flex: none;
	margin-left: 12rpx;
	width: 80rpx;
	height: 80rpx;
	border-radius: 50%;
	display: flex;
	align-items: center;
	justify-content: center;
	background-color: var(--accent);
	color: #ffffff;
	font-size: 30rpx;
}

.send-btn.disabled {
	opacity: 0.5;
}
</style>
