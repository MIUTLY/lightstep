<template>
	<view class="page-root" :class="themeClass" @touchstart="onUserTouch">
		<view class="page-safe" :style="statusBarStyle"></view>

		<!-- 顶栏：只有品牌 + 两个很小的入口，没有任何任务列表 / 打卡 -->
		<view class="nav">
			<view class="nav-left">
				<CatBuddy :pose="catPose" size="sm" />
				<view class="brand">
					<text class="brand-name">轻步</text>
					<text class="brand-sub">不催促 · 不吓你 · 不记仇</text>
				</view>
			</view>
			<view class="nav-right">
				<view class="nav-link" @tap.stop="goJournal">手帐</view>
				<view class="nav-link" @tap.stop="goSettings">设置</view>
			</view>
		</view>

		<!-- 对话区 -->
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

				<view v-if="!session.messages.length && !session.busy" class="placeholder">
					<text class="muted tiny">今天想做点什么？不想做也可以。</text>
				</view>

				<view id="bottom" class="anchor-bottom"></view>
			</view>
		</scroll-view>

		<!-- 5 件小事 + 回执入口 -->
		<view class="quick-wrap">
			<QuickActions @action="onQuick" />
		</view>

		<!-- 输入区 -->
		<view class="composer">
			<view class="icon-btn" @tap.stop="onVoice">
				<text class="icon-text">说</text>
			</view>
			<input
				class="composer-input"
				v-model="draft"
				:placeholder="placeholder"
				:focus="inputFocus"
				confirm-type="send"
				:confirm-hold="true"
				@confirm="onSend"
				@input="onUserTouch"
			/>
			<view class="send-btn" :class="{ disabled: !draft.trim() }" @tap.stop="onSend">
				<text>发</text>
			</view>
		</view>

		<SoftLine :text="recallText" />
	</view>
</template>

<script setup>
/**
 * 对话建任务页（策划书 F1 + 5 件小事 + 跨天交接）
 *
 * 这一页是唯一入口：说一句话 → 后端拆成极小的步骤 → 用户选个开始时间。
 * 页面本身不做任何「任务管理」，没有待办列表、没有今日目标、没有打卡。
 */
import { computed, nextTick, ref, watch } from 'vue'
import { onHide, onShow } from '@dcloudio/uni-app'

import CatBuddy from '@/components/CatBuddy.vue'
import ChatBubble from '@/components/ChatBubble.vue'
import QuickActions from '@/components/QuickActions.vue'
import SoftLine from '@/components/SoftLine.vue'

import { useSession } from '@/store/session.js'
import { useSettings } from '@/store/settings.js'
import { useUser } from '@/store/user.js'
import { useSoftRecall } from '@/composables/useSoftRecall.js'
import { catPoseOfSteps } from '@/utils/format.js'
import { getStatusBarHeight } from '@/utils/systemInfo.js'
import { explainVoiceUnavailable, isVoiceSupported, listenOnce } from '@/utils/voice.js'

const session = useSession()
const settings = useSettings()
const user = useUser()

/** custom 导航栏：自己让出状态栏高度（刘海屏） */
const statusBarStyle = 'height:' + getStatusBarHeight() + 'px;'

const draft = ref('')
const inputFocus = ref(false)
const anchor = ref('')
const todaySteps = ref(0)
const started = ref(false)

const themeClass = computed(() => (settings.sensory ? 'theme-sensory' : ''))

/** 小步的姿势跟着今日步数走（刚打开时完全瘫着） */
const catPose = computed(() => catPoseOfSteps(todaySteps.value))

const placeholder = computed(() =>
	session.noteMode ? '记点什么…（走神的时候写下来）' : '说点什么，或者点上面的一件小事…'
)

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
	settings.load()
	user.ensure()

	if (!started.value) {
		started.value = true
		await session.open()
	} else {
		// 从单步页回来：把状态对齐一次（可能已经在那边完成任务 / 收尾）
		await session.syncState()
	}

	refreshToday()
	scrollToBottom()
	resumeRecall()
})

onHide(() => {
	stopRecall()
})

/** 每次回到对话页都刷一下今日小结，用来决定小步的姿势 */
async function refreshToday() {
	const summary = await session.fetchTodaySummary()
	if (summary) todaySteps.value = summary.steps_done || 0
}

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

/** 点后端给的按钮 */
async function onLabel(label) {
	if (session.busy) return
	await session.dispatchLabel(label)
	scrollToBottom()
}

/** 5 件小事 */
async function onQuick(key) {
	if (session.busy) return

	if (key === 'note') {
		session.noteMode = true
		inputFocus.value = false
		nextTick(() => {
			inputFocus.value = true
		})
		return
	}

	if (key === 'receipt') {
		uni.navigateTo({ url: '/pages/receipt/receipt' })
		return
	}

	const textMap = {
		switch: '换件事',
		afk: '发呆',
		rest: '今天什么都不想干',
		gentle: '温柔收尾'
	}
	const text = textMap[key]
	if (!text) return
	await session.sendChat(text)
	resetRecall()
	refreshToday()
	scrollToBottom()
}

/** 发送 */
async function onSend() {
	const text = draft.value.trim()
	if (!text || session.busy) return

	draft.value = ''
	inputFocus.value = false

	if (session.noteMode) {
		session.noteMode = false
		await session.sendNote(text)
	} else {
		await session.sendChat(text)
	}

	resetRecall()
	refreshToday()
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

function goJournal() {
	uni.navigateTo({ url: '/pages/journal/journal' })
}

function goSettings() {
	uni.navigateTo({ url: '/pages/settings/settings' })
}

// 进入执行态就去单步页（策划书第二步到第四步的跳转）
watch(
	() => session.navIntent,
	(intent) => {
		if (!intent) return
		session.takeNavIntent()
		if (intent === 'focus') {
			uni.navigateTo({ url: '/pages/focus/focus' })
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
.page-root {
	display: flex;
	flex-direction: column;
	width: 100%;
	box-sizing: border-box;
	height: 100vh;
	overflow: hidden;
}

.nav {
	display: flex;
	align-items: center;
	justify-content: space-between;
	width: 100%;
	box-sizing: border-box;
	padding: 20rpx 24rpx 16rpx;
	border-bottom: 1rpx solid var(--line);
	background-color: var(--surface);
}

.nav-left {
	display: flex;
	align-items: center;
	min-width: 0;
}

.brand {
	margin-left: 14rpx;
	display: flex;
	flex-direction: column;
	min-width: 0;
	overflow: hidden;
}

.brand-name {
	font-size: 32rpx;
	font-weight: 600;
	letter-spacing: 2rpx;
	color: var(--ink);
}

.brand-sub {
	margin-top: 2rpx;
	font-size: 20rpx;
	color: var(--muted);
}

.nav-right {
	display: flex;
	align-items: center;
	flex: none;
}

.nav-link {
	margin-left: 24rpx;
	padding: 6rpx 4rpx;
	font-size: 24rpx;
	color: var(--muted);
}

.chat-scroll {
	flex: 1;
	width: 100%;
	box-sizing: border-box;
	height: 0;
	overflow-x: hidden;
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

.placeholder {
	display: flex;
	justify-content: center;
	padding: 80rpx 0;
}

.anchor-bottom {
	height: 20rpx;
}

.quick-wrap {
	width: 100%;
	box-sizing: border-box;
	overflow: hidden;
	padding: 12rpx 0;
	border-top: 1rpx solid var(--line);
	background-color: var(--surface);
}

.composer {
	display: flex;
	align-items: center;
	width: 100%;
	box-sizing: border-box;
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

.composer-input {
	flex: 1;
	width: 0;
	min-width: 0;
	height: 76rpx;
	padding: 0 22rpx;
	border-radius: 20rpx;
	border: 1rpx solid var(--line);
	background-color: var(--surface-soft);
	color: var(--ink);
	font-size: 28rpx;
}

.send-btn {
	flex: none;
	margin-left: 12rpx;
	padding: 0 28rpx;
	height: 76rpx;
	border-radius: 20rpx;
	display: flex;
	align-items: center;
	justify-content: center;
	background-color: var(--cat);
	color: #fdfaf5;
	font-size: 28rpx;
}

.send-btn.disabled {
	opacity: 0.5;
}
</style>
