<template>
	<view class="page-root" :class="themeClass" @touchstart="onUserTouch">
		<!-- 纸纹底图：小程序里本地图不能做 CSS background-image，用 image 铺在最底层 -->
		<image class="paper-bg" src="/static/paper-bg.jpg" mode="aspectFill" />

		<view class="content">
			<view class="page-safe" :style="statusBarStyle"></view>

			<!-- 顶栏：左上角 LightStep logo + 侧边栏按钮（三横线） -->
			<view class="nav">
				<text class="logo">LightStep</text>
				<view
					class="menu-btn"
					:hover-class="'menu-btn-hover'"
					:hover-stay-time="60"
					@tap.stop="openDrawer"
				>
					<view class="menu-line"></view>
					<view class="menu-line"></view>
					<view class="menu-line"></view>
				</view>
			</view>

			<!-- 初始态：气泡在小猫上方，输入框在小猫下方，整体水平居中 -->
			<view v-if="phase === 'intro'" class="stage" :class="{ leaving: leaving }">
				<view class="intro-hero">
					<view class="intro-bubble">
						<text class="intro-bubble-text">我们要开始做什么呢</text>
						<view class="intro-bubble-tail"></view>
					</view>
					<CatBuddy pose="sleep" size="hero" />
				</view>

				<view class="intro-input-row">
					<view class="input-pill">
						<input
							class="input-field"
							v-model="draft"
							placeholder="说点什么…"
							confirm-type="send"
							@confirm="onSend"
							@input="onUserTouch"
						/>
						<view
							class="send-arrow"
							:class="{ disabled: !draft.trim() }"
							:hover-class="draft.trim() ? 'send-arrow-hover' : ''"
							:hover-stay-time="60"
							@tap.stop="onSend"
						>
							<text class="send-arrow-icon">↑</text>
						</view>
					</view>
				</view>
			</view>

			<!-- 对话态：气泡列表（小步的消息左侧带圆形头像）/ 输入区 -->
			<template v-else>
				<scroll-view
					class="chat-scroll"
					scroll-y
					:scroll-into-view="anchor"
					:scroll-with-animation="!settings.sensory"
				>
					<view class="chat-inner">
						<ChatBubble v-for="m in session.messages" :key="m.id" :message="m" @label="onLabel" />

						<view v-if="session.busy" class="thinking">
							<text class="muted tiny">…</text>
						</view>

						<view id="bottom" class="anchor-bottom"></view>
					</view>
				</scroll-view>

				<!-- 回复结束后出现的「专注模式」入口 -->
				<view v-if="showFocusEntry" class="focus-entry">
					<view class="focus-btn" hover-class="focus-btn-hover" :hover-stay-time="60" @tap.stop="goFocusMode">
						<text class="focus-btn-text">专注模式</text>
						<text class="focus-btn-sub">{{ focusEntrySub }}</text>
					</view>
				</view>

				<!-- 输入区（初始态发送后从页面中部滑落到这里） -->
				<view class="composer">
					<view class="icon-btn" @tap.stop="onVoice">
						<text class="icon-text">说</text>
					</view>
					<view class="input-pill">
						<input
							class="input-field"
							v-model="draft"
							:placeholder="placeholder"
							:focus="inputFocus"
							confirm-type="send"
							:confirm-hold="true"
							@confirm="onSend"
							@input="onUserTouch"
						/>
						<view
							class="send-arrow"
							:class="{ disabled: !draft.trim() }"
							:hover-class="draft.trim() ? 'send-arrow-hover' : ''"
							:hover-stay-time="60"
							@tap.stop="onSend"
						>
							<text class="send-arrow-icon">↑</text>
						</view>
					</view>
				</view>
			</template>

			<!-- 左侧抽屉：手账 / 设置（由右上角三横线唤出） -->
			<SideDrawer ref="drawer" :edge-handle="false" current="chat" />

			<SoftLine :text="recallText" />
            <FocusReceiptDialog v-if="pendingReceiptRound" :round="pendingReceiptRound" :flow="focusFlow" @closed="closeReceiptDialog" />
		</view>
	</view>
</template>

<script setup>
/**
 * 对话建任务页（策划书 F1 + 5 件小事 + 跨天交接）
 *
 * 这一页是唯一的功能入口：说一句话 → 后端拆成极小的步骤 → 用户选个开始时间。
 * 页面本身不做任何「任务管理」，没有待办列表、没有今日目标、没有打卡。
 *
 * 两个阶段：
 *   - intro（初始态）：左上角 LightStep logo + 三横线按钮；小猫水平居中，
 *     头顶浮着「我们要开始做什么呢」气泡，脚下方是初始输入框
 *   - chat（对话态）：第一次发送后，小猫和气泡上滑消失、输入区滑落到屏幕底部，
 *     切成气泡列表（小步的消息左侧带圆形头像）+ 输入区
 *
 * 底图是 static/paper-bg.jpg 的纸纹（小程序本地图不能当 CSS 背景，用 image 铺底）。
 */
import { computed, nextTick, ref, watch } from 'vue'
import { onHide, onShow } from '@dcloudio/uni-app'

import CatBuddy from '@/components/CatBuddy.vue'
import ChatBubble from '@/components/ChatBubble.vue'
import SoftLine from '@/components/SoftLine.vue'
import SideDrawer from '@/components/SideDrawer.vue'
import FocusReceiptDialog from '@/components/FocusReceiptDialog.vue'
import { createFocusFlow } from '@/utils/focusFlow.js'

import { useSession } from '@/store/session.js'
import { useSettings } from '@/store/settings.js'
import { useToday } from '@/store/today.js'
import { useUser } from '@/store/user.js'
import { useSoftRecall } from '@/composables/useSoftRecall.js'
import { getStatusBarHeight } from '@/utils/systemInfo.js'
import { explainVoiceUnavailable, isVoiceSupported, listenOnce } from '@/utils/voice.js'

const session = useSession()
const settings = useSettings()
const today = useToday()
const user = useUser()
const focusFlow = createFocusFlow({ today, userId: () => user.current() })
const pendingReceiptRound = ref(null)
let receiptPageVisible = false
function refreshReceiptDialog() { pendingReceiptRound.value = focusFlow.pending() }
function closeReceiptDialog() { pendingReceiptRound.value = null }

/** custom 导航栏：自己让出状态栏高度（刘海屏） */
const statusBarStyle = 'height:' + getStatusBarHeight() + 'px;'

const draft = ref('')
const inputFocus = ref(false)
const anchor = ref('')
const started = ref(false)

const themeClass = computed(() => (settings.sensory ? 'theme-sensory' : ''))

/* ---------------- 阶段切换：intro（小猫+气泡+输入框） → chat（对话界面） ---------------- */

/** 还没说过话、也没有进行中的任务 → 初始态（和旧版 showHero 同一套判定） */
const isFresh = computed(() => !session.hasTalked && !session.task)
const phase = ref(isFresh.value ? 'intro' : 'chat')
/** 初始态离场动画进行中（小猫气泡上滑、输入区下落） */
const leaving = ref(false)

// 冷启动 open() 同步到历史会话时，直接切成对话界面（不播动画）
watch(isFresh, (fresh) => {
	if (!fresh && phase.value === 'intro' && !leaving.value) phase.value = 'chat'
})

/**
 * 输入框提示语。
 *
 * 澄清（范围补充）有两条来源，都要认：
 *   1. 新主流程（PR #16 起默认走 /api/chat → 今日备忘录）：
 *      待澄清项在 GET /api/today 的 clarifications[] 里，session.generation 是 null；
 *   2. 旧单任务流程（workflow:'legacy'）：generation.status = 'needs_clarification'。
 *
 * 澄清的问题问的是「哪份作业、约定做几题」这类范围，不是要用户交答案或选项
 * （后端 ACTION_SUPPORT_POLICY 明确不索要题目全文/答案），所以提示语只用「补充：」，
 * 不写「写下你的答案」，免得用户以为要交作业。
 */
const clarifyQuestion = computed(() => {
	const first = today.firstClarification()
	if (first && first.question) return first.question
	const g = session.generation
	if (g && g.status === 'needs_clarification' && g.question) return g.question
	return ''
})

const needsClarify = computed(() => !!clarifyQuestion.value)

const placeholder = computed(() => {
	if (session.noteMode) return '记点什么…（走神的时候写下来）'
	if (needsClarify.value) {
		return '补充：' + clarifyQuestion.value.slice(0, 24) + '…'
	}
	return '说点什么，或者点上面的一件小事…'
})

/**
 * 「专注模式」入口的出现时机。
 * 需求是「用户发送后、小步回复结束后自动弹出」，所以用 busy 归零来判定。
 *
 * 后端 PR #16 起，回复里带 can_enter_focus：只要还有任务没澄清完就是 false。
 * 这种情况不弹入口 —— 用户直接在对话里回答小步的追问（/api/chat 会把它路由成
 * 「回答某个待澄清问题」），答完 can_enter_focus 变 true，入口才出现。
 */
const showFocusEntry = computed(() => {
	if (!session.hasTalked || session.busy) return false
	if (today.hasFocus()) return true
	if (!today.items.length) return false
	return today.canEnterFocus !== false
})

const focusEntrySub = computed(() => {
	if (today.hasFocus()) return '看这一步和后面还有几步'
	if (today.hasClarifications()) return '先把小步的问题答完'
	return '去备忘录挑一件'
})

function goFocusMode() {
	// 需求：主界面点「专注模式」必须进独立的专注模式界面（不再绕去备忘录）。
	// 没有正在专注的任务时，专注模式页会用建议项自己开一项（见 pages/focusmode onShow）。
	uni.navigateTo({ url: '/pages/focusmode/focusmode' })
}

/* ---------------- 侧边栏 ---------------- */

const drawer = ref(null)

function openDrawer() {
	if (drawer.value) drawer.value.open()
}

// 温和召回：5 分钟没碰屏幕才浮一句话，最多 2 次；勿扰开关关掉它
const {
	text: recallText,
	poke: pokeRecall,
	resume: resumeRecall,
	stop: stopRecall,
	reset: resetRecall
} = useSoftRecall({
	enabled: () => !settings.dnd
})

onShow(async () => {
    receiptPageVisible = true
	settings.load()
	user.ensure()

	if (!started.value) {
		started.value = true
		await session.open()
	} else {
		// 从单步页回来：把状态对齐一次（可能已经在那边完成任务 / 收尾）
		await session.syncState()
	}

	scrollToBottom()
	resumeRecall()
	// 今日清单 / 专注状态可能是从备忘录页改过的，回来时对齐一次
    const view = await today.load()
    if (receiptPageVisible && view && !today.hasFocus()) {
        try {
            const receipts = (today.events || []).filter(e => e.kind === 'receipt')
            focusFlow.recover(receipts, false)
            refreshReceiptDialog()
            for (const receipt of receipts) await today.ack(receipt.id)
        } catch (e) { uni.showToast({ title: e.message || '回执暂时未能打开，请重试', icon: 'none' }) }
    }
})

onHide(() => {
    receiptPageVisible = false
	stopRecall()
})

function scrollToBottom() {
	anchor.value = ''
	nextTick(() => {
		anchor.value = 'bottom'
	})
}

/** 任何触摸都算「人在」，重置召回计时 */
function onUserTouch() {
	pokeRecall()
}

/*
 * 5/10 分钟预约与提醒轮询已整体移除：
 *   后端 2026-11-07 起取消全部任务计时，/api/reminders/poll 返回 410 TASK_TIMERS_REMOVED，
 *   task.start_due_at 恒为 null。这里不再起任何定时器。
 */

/** 点后端给的按钮 */
async function onLabel(label) {
	if (session.busy) return
	await session.dispatchLabel(label)
	scrollToBottom()
}

/** 发送（初始态的第一次发送同时触发 阶段切换 动画） */
async function onSend() {
	const text = draft.value.trim()
	if (!text || session.busy) return

	draft.value = ''
	inputFocus.value = false

	// 初始态 → 对话态：小猫和气泡上滑消失，输入框落到页面底部
	if (phase.value === 'intro') {
		leaving.value = true
		setTimeout(() => {
			phase.value = 'chat'
			leaving.value = false
			scrollToBottom()
		}, 340)
	}

	if (session.noteMode) {
		session.noteMode = false
		await session.sendNote(text)
	} else {
		/*
		 * 回复走 /api/chat 的 chat 路由：后端自己判断这句是闲聊 / 回答待澄清问题 / 新任务。
		 * 但模型偶尔会把「写数学作业，第3章1到10题」这类回答误判成新任务，
		 * 所以当列表里还有待澄清项时，把「在回答哪一项」显式写进消息（实测能稳定命中 answer）。
		 */
		const first = today.firstClarification()
		const outgoing = first ? '关于「' + first.title + '」：' + text : text
		await session.sendChat(outgoing)
		// 默认 /api/chat 现在走「今日备忘录」：回复里不再有 task，清单在 /api/today 里，
		// 所以每次说完顺手把清单拉一次，下面的「专注模式」入口才有依据。
		await today.load()
	}

	resetRecall()
	scrollToBottom()
}

/** 语音：有微信同声传译插件就用，没有就老实说「还没接」 */
async function onVoice() {
	if (!isVoiceSupported()) {
		explainVoiceUnavailable()
		return
	}
	try {
		const text = await listenOnce()
		if (!text) {
			uni.showToast({ title: '没听清，再说一次？', icon: 'none' })
			return
		}
		draft.value = text
		await onSend()
	} catch (err) {
		uni.showToast({ title: err.message || '语音识别失败', icon: 'none' })
	}
}

// 进入执行态就进专注模式。
// ⚠️ 这里原本跳的是旧版「单步执行页」pages/focus/focus（策划书 F2 那一版），
// 那一页不在 Figma 设计稿里，已经下线；专注现在只有 pages/focusmode 一个界面。
watch(
	() => session.navIntent,
	(intent) => {
		if (!intent) return
		session.takeNavIntent()
		if (intent === 'focus') {
			uni.navigateTo({ url: '/pages/focusmode/focusmode' })
		}
	}
)

// 新消息进来就滚到底
watch(
	() => session.messages.length,
	() => scrollToBottom()
)
</script>

<style scoped>
/* ---------- 底图与骨架 ---------- */

/* 纸纹底图铺满全屏（本地图不能做 CSS background，只能用 image 元素） */
.paper-bg {
	position: absolute;
	left: 0;
	top: 0;
	width: 100%;
	height: 100%;
}

.page-root {
	position: relative;
	width: 100%;
	height: 100vh;
	overflow: hidden;
	background-color: var(--bg);
}

/* 真正的内容层：抬到底图上面 */
.content {
	position: relative;
	z-index: 1;
	display: flex;
	flex-direction: column;
	width: 100%;
	height: 100vh;
	box-sizing: border-box;
	overflow: hidden;
}

.page-safe {
	flex: none;
	/* 具体高度由页面用 :style 绑定状态栏高度（见 utils/systemInfo.js） */
}

/* ---------- 顶栏：logo + 三横线 ---------- */

.nav {
	display: flex;
	align-items: center;
	justify-content: flex-start;
	width: 100%;
	box-sizing: border-box;
	padding: 16rpx 24rpx;
}

.logo {
	font-size: 30rpx;
	font-weight: 600;
	letter-spacing: 2rpx;
	color: #5e5d62;
}

.menu-btn {
	flex: none;
	width: 64rpx;
	height: 64rpx;
	margin-left: 24rpx;
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	border-radius: 16rpx;
	border: 1rpx solid var(--line);
	background-color: var(--surface);
}

.menu-btn-hover {
	background-color: var(--surface-soft);
}

.menu-line {
	width: 30rpx;
	height: 4rpx;
	margin: 3rpx 0;
	border-radius: 2rpx;
	background-color: #5e5d62;
}

/* ---------- 初始态：气泡 + 小猫 + 输入框 ---------- */

.stage {
	flex: 1;
	height: 0;
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 0 56rpx 40rpx;
	box-sizing: border-box;
}

.intro-hero {
	display: flex;
	flex-direction: column;
	align-items: center;
	transition-property: transform, opacity;
	transition-duration: 0.32s;
	transition-timing-function: ease;
}

.intro-bubble {
	position: relative;
	margin-bottom: 40rpx;
	padding: 18rpx 30rpx;
	border-radius: 24rpx;
	border: 1rpx solid var(--line);
	background-color: var(--surface);
}

.intro-bubble-text {
	font-size: 30rpx;
	letter-spacing: 1rpx;
	color: var(--ink-soft);
}

/* 气泡尾巴：旋转 45° 的小方块，指向下面的小猫 */
.intro-bubble-tail {
	position: absolute;
	left: 50%;
	bottom: -10rpx;
	width: 20rpx;
	height: 20rpx;
	margin-left: -10rpx;
	background-color: var(--surface);
	border-right: 1rpx solid var(--line);
	border-bottom: 1rpx solid var(--line);
	transform: rotate(45deg);
}

.intro-input-row {
	display: flex;
	align-items: center;
	width: 100%;
	max-width: 640rpx;
	margin-top: 56rpx;
	transition-property: transform, opacity;
	transition-duration: 0.32s;
	transition-timing-function: ease;
}

/* ---------- 输入框：发送按钮（小箭头，四角圆边）内嵌在输入框里 ---------- */

.input-pill {
	flex: 1;
	display: flex;
	align-items: center;
	height: 84rpx;
	box-sizing: border-box;
	padding: 0 10rpx 0 26rpx;
	border-radius: 24rpx;
	border: 1rpx solid var(--line);
	background-color: var(--surface);
}

.input-field {
	flex: 1;
	width: 0;
	min-width: 0;
	height: 100%;
	font-size: 28rpx;
	color: var(--ink);
	background-color: transparent;
	border: none;
}

.send-arrow {
	flex: none;
	width: 64rpx;
	height: 64rpx;
	margin-left: 12rpx;
	border-radius: 18rpx;
	display: flex;
	align-items: center;
	justify-content: center;
	background-color: var(--cat);
}

.send-arrow-hover {
	opacity: 0.85;
}

.send-arrow-icon {
	font-size: 32rpx;
	line-height: 1;
	color: #fdfaf5;
}

.send-arrow.disabled {
	opacity: 0.4;
}

/* 离场动画：小猫和气泡上滑消失，输入框滑向屏幕底部 */
.stage.leaving .intro-hero {
	transform: translateY(-46vh);
	opacity: 0;
}

.stage.leaving .intro-input-row {
	transform: translateY(46vh);
	opacity: 0;
}

/* ---------- 对话态 ---------- */

.chat-scroll {
	flex: 1;
	width: 100%;
	box-sizing: border-box;
	height: 0;
	overflow-x: hidden;
	animation: rise-in 0.3s ease;
}

.chat-inner {
	width: 100%;
	box-sizing: border-box;
	padding: 24rpx 24rpx 8rpx;
}

.thinking {
	display: flex;
	padding: 4rpx 8rpx 20rpx;
}

.anchor-bottom {
	height: 20rpx;
}

/* 对话态各区块进场（从初始态切换过来时） */
.reminder-bar,
.composer {
	animation: rise-in 0.3s ease;
}

@keyframes rise-in {
	from {
		opacity: 0;
		transform: translateY(24rpx);
	}
	to {
		opacity: 1;
		transform: translateY(0);
	}
}

/* ---------- 专注模式入口 ---------- */

.focus-entry {
	display: flex;
	justify-content: center;
	padding: 8rpx 24rpx 12rpx;
}

.focus-btn {
	display: flex;
	flex-direction: column;
	align-items: center;
	padding: 12rpx 40rpx;
	border-radius: 999rpx;
	border: 1rpx solid var(--accent);
	background-color: var(--accent-soft);
}

.focus-btn-hover {
	opacity: 0.86;
}

.focus-btn-text {
	font-size: 26rpx;
	font-weight: 600;
	color: var(--accent-deep);
}

.focus-btn-sub {
	margin-top: 2rpx;
	font-size: 20rpx;
	color: var(--muted);
}

/* ---------- 预约提示条 ---------- */

.reminder-bar {
	display: flex;
	align-items: center;
	justify-content: space-between;
	width: 100%;
	box-sizing: border-box;
	padding: 12rpx 24rpx;
	background-color: var(--accent-soft);
	border-top: 1rpx solid var(--line);
}

.reminder-text {
	flex: 1;
	font-size: 24rpx;
	color: var(--accent-deep);
}

.reminder-btn {
	flex: none;
	margin-left: 16rpx;
	padding: 8rpx 20rpx;
	border-radius: 999rpx;
	border: 1rpx solid var(--accent);
	background-color: var(--surface);
	color: var(--accent-deep);
	font-size: 22rpx;
	line-height: 1.4;
}

.composer {
	display: flex;
	align-items: center;
	width: 100%;
	box-sizing: border-box;
	/* 底部安全区在这里自己留 */
	padding: 16rpx 24rpx calc(16rpx + env(safe-area-inset-bottom));
	background-color: var(--surface);
	border-top: 1rpx solid var(--line);
}

.icon-btn {
	flex: none;
	width: 72rpx;
	height: 72rpx;
	margin-right: 12rpx;
	border-radius: 50%;
	border: 1rpx solid var(--line);
	display: flex;
	align-items: center;
	justify-content: center;
	background-color: var(--surface-soft);
}

.icon-text {
	font-size: 24rpx;
	color: var(--ink-soft);
}
</style>
