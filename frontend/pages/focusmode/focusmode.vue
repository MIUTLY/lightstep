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

		<!-- 任务名（设计稿 x=246 y=132 宽309 55px 左对齐；换算成 rpx 见下方样式表） -->
		<view class="wall">
			<text class="task-title" :class="titleSizeClass">{{ taskTitle }}</text>
		</view>

		<!-- 当前这一步：设计稿里没有这一段，按产品需要单独放在标题下方（居中、不参与按钮定位） -->
		<view v-if="currentStep" class="task-step">
			<text>{{ currentStep }}</text>
		</view>

		<!-- 待澄清提示：落位在设计稿标题与「完成了」之间的空档（y 230~406rpx），
		     不压住三个按钮，也不用把下面的按钮往下推 -->
		<view v-if="pendingQuestion" class="clarify-card">
			<text class="clarify-text">{{ pendingQuestion }}</text>
			<text class="clarify-hint">回上一页把范围补一句，再回来开专注。</text>
		</view>

		<!-- 三个操作按钮：绝对坐标照抄设计稿，不再靠上下 margin 堆叠 -->
		<view class="pills">
			<view class="pill pill-done" :class="{ disabled: today.busy || transitionBusy || !hasFocus }" hover-class="pill-hover" @tap.stop="onDone">
				<text class="pill-text pill-text-done">完成了</text>
			</view>
			<view class="pill pill-heavier" :class="{ disabled: today.busy || transitionBusy || !hasFocus }" hover-class="pill-hover" @tap.stop="onHeavier">
				<text class="pill-text">重一点</text>
			</view>
			<view class="pill pill-lighter" :class="{ disabled: today.busy || transitionBusy || !hasFocus }" hover-class="pill-hover" @tap.stop="onLighter">
				<text class="pill-text">轻一点</text>
			</view>
		</view>

        <view v-if="retryNextId" class="clarify-card">
            <text>上一项已完成，下一项暂时没能开始。进度已保留。</text>
            <view @tap.stop="retryNextTask"><text>重试下一项</text></view>
        </view>

		<!-- 左侧：粉红书本（设计稿 x=-14 y=583，274×131；左边故意出血到画布外）。
		     点它打开「思绪倾倒」；澄清态先让位给上方的问题卡片 -->
		<view v-if="!pendingQuestion" class="note-btn" hover-class="note-hover" @tap.stop="openThoughts">
			<image class="note-img" src="/static/focus-book-1.png" mode="aspectFill" />
		</view>

		<!-- 右下角桌宠：2026-11-08 起素材由后端托管，按「表现计步」切状态图。
		     单击不做任何事；双击打开新增任务弹窗（原「小布聊天」）；
		     前台 300 秒没操作只换成走神图，不改任何服务器状态。 -->
		<view class="floor-cat" @touchstart="onUserTouch" @tap="onPetTap">
			<image class="floor-cat-img" :src="petSrc" mode="aspectFit" @error="onPetError" />
		</view>

		<!-- 底部：就到这儿吧（设计稿距画布底边 152px ≈ 148rpx） -->
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

	</view>
</template>

<script setup>
/**
 * 专注模式（严格按 Figma 设计稿还原）
 *
 * 设计稿：fileKey a4LwTwEh3akDn7IkZygSh7 / node 0:1，画布 768×1376（与 static/focus-bg.jpg 同尺寸）
 * 换算规则：rpx = 设计稿 px × 750 ÷ 768（≈0.9766）。所有坐标都从画布左上角量起。
 *
 * 元素           设计稿 px (x,y,w,h)      → rpx
 *   喇叭图标       54, 67, 56×56         → 53, 65, 55×55
 *   任务名        246, 132, 309×81      → 240, 129, 302 宽 / 54rpx 左对齐
 *   完成了        200, 426, 400×70      → 195, 416, 391×68
 *   重一点        246, 556, 290×48      → 240, 543, 283×47
 *   轻一点        246, 660, 290×48      → 240, 645, 283×47
 *   粉红书本      -14, 583, 274×131     → -14, 569, 268×128（左边出血到画布外）
 *   地板猫        364, 813, 404×375     → 右缘贴齐, 距底 184, 394×366（纯静态）
 *   就到这儿吧    246, 1174, 290×50     → 240, 距底 148, 283×49
 *
 * 定位策略：上半部分（喇叭/标题/三个按钮/书本）用绝对坐标从画布顶边量起，
 * 换行或澄清卡片都不会推动按钮；「地板猫」和「就到这儿吧」按设计稿与画布底边的
 * 间距（188px / 152px）从底边锚定，这样换到不同高度的手机上不会浮在半空。
 *
 * 按钮规格：白底 rgba(255,255,255,.84)、边框 #F9E1C4 2px、圆角 47.5px、
 *          外发光 0 0 14.9px rgba(254,214,108,.6) + 内发光 inset 0 0 27.1px rgba(255,238,192,1)，
 *          文字 #5E5D62（就到这儿吧 #333333）。
 *
 * 交互：书本 → 思绪倾倒卡片；就到这儿吧 → 成功结束后回对话页弹回执，用户填写并主动保存。
 *      地板猫在设计稿里只是画面的一部分（不是按钮），所以不绑任何点击/悬停。
 */
import { computed, nextTick, ref } from 'vue'
import { onHide, onShow } from '@dcloudio/uni-app'

import { useSettings } from '@/store/settings.js'
import { useToday } from '@/store/today.js'
import { useUser } from '@/store/user.js'
import { createFocusFlow } from '@/utils/focusFlow.js'
import {
	idlePetUrl,
	idleTimeoutSeconds,
	loadManifest,
	petImageUrl
} from '@/utils/presentation.js'
import { getStatusBarHeight } from '@/utils/systemInfo.js'

const settings = useSettings()
const today = useToday()
const flow = createFocusFlow({ today, userId: () => useUser().current() })
const transitionBusy = ref(false)
const retryNextId = ref('')
let pageVisible = true

const themeClass = computed(() => (settings.sensory ? 'theme-sensory' : ''))
const statusBarStyle = 'height:' + getStatusBarHeight() + 'px;'

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
	return '正在恢复任务…'
})

/**
 * 任务名不折行：按「字号当量宽度」逐档降字号。
 * 中文字宽≈1 个字号、半角≈0.55 个字号；标题区宽 638rpx，留 2 成余量 ≈523rpx 可用。
 */
const titleSizeClass = computed(() => {
	const title = String(taskTitle.value || '')
	let em = 0
	for (const ch of title) em += /[\x00-\xff]/.test(ch) ? 0.55 : 1
	const budget = 638 * 0.82
	if (em * 54 <= budget) return ''
	if (em * 46 <= budget) return 'title-md'
	if (em * 38 <= budget) return 'title-sm'
	return 'title-xs'
})

const currentStep = computed(() => {
	const f = today.focus
	return f && f.step ? f.step.current_step || '' : ''
})

const doneCount = computed(() => today.completedActions().length)

/* ---------------- 桌宠：后端托管素材 + 表现计步 + 空闲换走神图 ---------------- */

/** 素材清单（/api/assets/manifest，进程内缓存）；拿不到就只用本地兜底图 */
const manifest = ref(null)
/** 是否处于「前台 300 秒没操作」状态：只影响显示哪张图 */
const idleNow = ref(false)
/** 网络素材加载失败 → 回落设计稿那张地板猫 */
const petBroken = ref(false)
let idleTimer = null

/** 后端下发的当前桌宠（focus.presentation.normal_pet） */
const normalPetSrc = computed(() => petImageUrl(today.focusPresentation()))

/** 走神图（manifest.idle_policy.idle_pet → pets.distracted） */
const idlePetSrc = computed(() => idlePetUrl(manifest.value))

const petSrc = computed(() => {
	if (petBroken.value) return '/static/focus-book-2.png'
	if (idleNow.value && idlePetSrc.value) return idlePetSrc.value
	return normalPetSrc.value || '/static/focus-book-2.png'
})

const idleSeconds = computed(() => idleTimeoutSeconds(today.policy(), manifest.value))

function clearIdleTimer() {
	if (idleTimer) {
		clearTimeout(idleTimer)
		idleTimer = null
	}
}

function scheduleIdleTimer() {
	clearIdleTimer()
	if (!today.hasFocus()) return
	idleTimer = setTimeout(() => {
		idleNow.value = true
		idleTimer = null
	}, idleSeconds.value * 1000)
}

/** 任何触摸 / 输入都算「人还在」：恢复正常猫并重新计时 */
function noteActivity() {
	if (idleNow.value) idleNow.value = false
	scheduleIdleTimer()
}

function onPetError() {
	petBroken.value = true
}

/** 单击无动作；300ms 内连点两下 = 打开新增任务弹窗 */
let lastPetTapAt = 0
function onPetTap() {
	noteActivity()
	const now = Date.now()
	if (now - lastPetTapAt < 300) {
		lastPetTapAt = 0
		toggleChat()
		return
	}
	lastPetTapAt = now
}

/* ---------------- 进页面自动开一项 ---------------- */

onShow(async () => {
    pageVisible = true
	settings.load()
    if (transitionBusy.value || today.busy) return
	loadManifest().then((m) => {
		if (m) manifest.value = m
	})
	if (!today.loaded) await today.load()
	if (today.hasFocus()) { flow.begin(); scheduleIdleTimer(); return }
	if (today.pendingSelect || today.hasClarifications()) { backToChat(); return }
    if (flow.pending() || (today.events || []).some(e => e.kind === 'receipt' && e.outcome === 'interrupted')) {
        flow.recover(today.events, false); backToChat(); return
    }
	// 还有没澄清完的任务时不要抢着开专注（后端 can_enter_focus=false）
	if (today.canEnterFocus === false || today.hasClarifications()) return

	const id = today.suggestedItemId || (today.items[0] && today.items[0].id)
	if (!id) { backToChat(); return }
	const view = await today.select(id)
	if (!view) { backToChat(); return }
	const status = view.operation && view.operation.status
	if (status === 'needs_clarification') {
		const first = today.firstClarification()
		today.pendingSelect = { itemId: id, question: (first && first.question) || view.reply || '还需要补充一点信息' }
        backToChat(); return
	} else if (status === 'failed') {
		uni.showToast({ title: (view.operation.error && view.operation.error.message) || '没能开始', icon: 'none' })
        backToChat(); return
	}
	scheduleIdleTimer()
})

onHide(() => {
    pageVisible = false
	// 退到后台就取消计时（协议：on_background=cancel），回来重新等满 300 秒
	clearIdleTimer()
	idleNow.value = false
})

/* ---------------- 喇叭（设计稿里左上角那个图标） ---------------- */

function onSound() {
	// 后端没有 TTS，也没有朗读接口；这里如实说明，不假装能播。
	uni.showToast({ title: '朗读还没接，先用眼睛看这一步', icon: 'none' })
}

/* ---------------- 三个按钮 ---------------- */

async function onDone() {
    if (transitionBusy.value || today.busy || !hasFocus.value) return
    transitionBusy.value = true; noteActivity()
    try { await handleTransition(await flow.complete()) }
    catch (e) {
        if (!today.hasFocus()) retryNextId.value = today.suggestedItemId || ''
        uni.showToast({ title: e.message || '没能继续，请重试', icon: 'none' })
    }
    finally { transitionBusy.value = false }
}
async function handleTransition(result) {
    if (result.status === 'next_failed') {
        retryNextId.value = result.nextItemId
        uni.showToast({ title: today.lastError || '下一项未开始，点重试继续', icon: 'none' })
    } else if (result.status === 'finished' || result.status === 'clarification') {
        retryNextId.value = ''; backToChat()
    } else if (result.status === 'executing') {
        retryNextId.value = ''; scheduleIdleTimer()
    } else if (result.status === 'failed') {
        uni.showToast({ title: today.lastError || '这次没成功，请重试', icon: 'none' })
    }
}
async function retryNextTask() {
    if (transitionBusy.value || !retryNextId.value) return
    transitionBusy.value = true
    try { await handleTransition(await flow.retryNext(retryNextId.value)) }
    catch (e) { uni.showToast({ title: e.message, icon: 'none' }) }
    finally { transitionBusy.value = false }
}

async function onLighter() {
	if (today.busy || transitionBusy || !hasFocus.value) return
	noteActivity()
	await today.resize('smaller')
}

async function onHeavier() {
	if (today.busy || transitionBusy || !hasFocus.value) return
	noteActivity()
	await today.resize('bigger')
}

/* ---------------- 就到这儿吧 ---------------- */

const exiting = ref(false)

async function onExit() {
    if (exiting.value || transitionBusy.value || today.busy) return
    exiting.value = true; noteActivity()
    try { await handleTransition(await flow.end()) }
    catch (e) { uni.showToast({ title: e.message || '没能结束，请重试', icon: 'none' }) }
    finally { exiting.value = false }
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

/**
 * 专注页内的「加一件 / 补范围」聊天框开关。
 *
 * ⚠️ 设计稿里地板猫只是画面的一部分，不是按钮 —— 按设计稿要求已经去掉猫的点击与悬停，
 * 所以这个聊天框目前**没有入口**（保留实现，方便以后挂到别的位置，例如书本长按或顶部小图标）。
 * 要恢复：把 @tap.stop="toggleChat"（和 hover-class）加回 .floor-cat 即可。
 */
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

function onUserTouch() {
	// 触摸也算「人还在」：走神图恢复正常猫，空闲计时重新开始
	noteActivity()
}

function backToChat() {
    if (!pageVisible) return
    clearIdleTimer()
    uni.reLaunch({ url: '/pages/chat/chat' })
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

/* 左上角喇叭：设计稿 56×56 @ (54, 67) → 55×55 @ (53, 65) */
.sound-btn {
	position: absolute;
	left: 53rpx;
	top: 65rpx;
	z-index: 5;
	width: 55rpx;
	height: 55rpx;
}

.sound-hover {
	opacity: 0.7;
}

/* 喇叭：一个方块 + 一个三角 + 两道弧 */
.spk {
	position: relative;
	width: 55rpx;
	height: 55rpx;
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

/* 任务名：设计稿是 x=246 y=132 宽309，55px 左对齐、只放得下 5 个字。
   真实任务名经常更长（「背50个英语单词」就 8 个字），照设计稿那样窄就会折行、
   还会压到下面的「当前这一步」。所以这里放宽成整行居中 + 按字数降字号，
   保证**一行放下不换行**（设计稿那种 5 字标题仍是最初的 54rpx）。 */
.wall {
	position: absolute;
	left: 56rpx;
	right: 56rpx;
	top: 129rpx;
	z-index: 3;
	/* 极端长的标题宁可两边裁掉，也不要折行去压下面的「当前这一步」 */
	overflow: hidden;
}

/* 任务名：设计稿 55px → 54rpx */
.task-title {
	display: block;
	font-size: 54rpx;
	line-height: 1.47;
	text-align: center;
	color: #5e5d62;
	letter-spacing: 2rpx;
	/* 绝对不折行；字号按字数由 titleSizeClass 往下调，长标题放得下 */
	white-space: nowrap;
}

.task-title.title-md {
	font-size: 46rpx;
	letter-spacing: 1rpx;
}

.task-title.title-sm {
	font-size: 38rpx;
	letter-spacing: 0;
}

.task-title.title-xs {
	font-size: 32rpx;
	letter-spacing: 0;
}

.task-step {
	position: absolute;
	left: 95rpx;
	top: 220rpx;
	width: 560rpx;
	z-index: 3;
}

.task-step text {
	font-size: 24rpx;
	line-height: 1.6;
	text-align: center;
	color: #8b8891;
	/* 后端会把父任务的当前动作明细用换行并进 current_step，保留换行 */
	white-space: pre-line;
}

/* 待澄清卡片：设计稿没有这个元素，放进标题与「完成了」之间的空档
   （129+79=208 之下，416 之上），不压按钮、也不把按钮往下挤 */
.clarify-card {
	position: absolute;
	left: 115rpx;
	top: 230rpx;
	z-index: 3;
	width: 520rpx;
	max-height: 176rpx;
	overflow: hidden;
	box-sizing: border-box;
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

/* 容器只做定位基准（高度 0）：三个按钮全部用设计稿绝对坐标，
   这样标题换成两行、或出现澄清卡片时，按钮位置都不会被推动 */
.pills {
	position: absolute;
	left: 0;
	top: 416rpx;
	width: 100%;
	height: 0;
	z-index: 2;
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

/* 设计稿 → rpx（px × 750/768）：
   完成了 200,426 400×70 → left 195 top   0 391×68
   重一点 246,556 290×48 → left 240 top 127 283×47
   轻一点 246,660 290×48 → left 240 top 229 283×47
   （三个都用绝对坐标；「完成了」比下面两个右偏 9rpx 是设计稿本身的位置，照抄） */
.pill-done {
	position: absolute;
	left: 195rpx;
	top: 0;
	width: 391rpx;
	height: 68rpx;
}

.pill-heavier {
	position: absolute;
	left: 240rpx;
	top: 127rpx;
	width: 283rpx;
	height: 47rpx;
}

.pill-lighter {
	position: absolute;
	left: 240rpx;
	top: 229rpx;
	width: 283rpx;
	height: 47rpx;
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

/* 粉红书本：设计稿 274×131 @ (-14, 583) → 268×128 @ (-14, 569)
   左边故意出血到画布外（设计稿就是负坐标），所以不要拿可视内容去猜尺寸：
   PNG 里四周有透明留白，必须整块按 268×128 渲染才和设计稿对得上 */
.note-btn {
	position: absolute;
	left: -14rpx;
	top: 569rpx;
	z-index: 4;
	width: 268rpx;
	height: 128rpx;
}

.note-hover {
	opacity: 0.82;
}

.note-img {
	display: block;
	width: 268rpx;
	height: 128rpx;
}

/* 地板上的小猫：设计稿 404×375 @ (364, 813) → 394×366，右边缘贴齐画布（right: 0），
   距画布底边 188px → 184rpx。设计稿里它是静态装饰，所以这里没有任何点击态/悬停态 */
/* 地板猫 / 桌宠：固定容器 + aspectFit，换状态图时容器尺寸不变，点击区域不跳 */
.floor-cat {
	position: absolute;
	right: 0;
	bottom: 184rpx;
	z-index: 6;
	width: 394rpx;
	height: 366rpx;
}

.floor-cat-img {
	display: block;
	width: 394rpx;
	height: 366rpx;
}

/* ---------- 底部：就到这儿吧 ---------- */

/* 就到这儿吧：设计稿 290×50 @ (246, 1174)，距画布底边 152px → 148rpx；
   底部按到画布底边的间距锚定，这样换到不同高度的手机上按钮不会浮在半空 */
.bottom {
	position: absolute;
	left: 240rpx;
	bottom: calc(148rpx + env(safe-area-inset-bottom));
	z-index: 5;
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
