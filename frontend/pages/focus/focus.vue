<template>
	<view class="page-root" :class="themeClass" @touchstart="onUserTouch">
		<view class="page-safe" :style="statusBarStyle"></view>

		<!-- 顶部：两个极小的东西，不抢注意力 -->
		<view class="top-row">
			<view class="tiny-link" @tap.stop="collapse">
				<text>收起来</text>
			</view>
			<view class="tiny-link" @tap.stop="toggleDnd">
				<text>{{ settings.dnd ? '勿扰中' : '勿扰' }}</text>
			</view>
		</view>

		<!-- 舞台：全屏只有当前这一步，没有进度条 / 倒计时 / 下一步预览 -->
		<view class="stage">
			<view class="step-line" :class="animClass">
				<text class="step-text">{{ currentStep }}</text>
			</view>
		</view>

		<FiveMinuteChoice />

		<!-- 底部：两个按钮 + 一句很轻的「还是有点重」 -->
		<view class="bottom">
			<view class="main-btn primary" hover-class="main-btn-hover" :hover-stay-time="60" @tap.stop="onDone">
				<text>这步做完了</text>
			</view>
			<view class="main-btn" hover-class="main-btn-hover" :hover-stay-time="60" @tap.stop="onExit">
				<text>今天到这吧</text>
			</view>
			<view class="heavy-link" @tap.stop="onHeavy">
				<text>还是有点重</text>
			</view>
		</view>

		<!-- 小步缩在角落（策划书 9.4：不要放中间当主角） -->
		<view class="cat-corner">
			<CatBuddy :pose="catPose" size="md" />
		</view>

		<SoftLine :text="recallText" />
	</view>
</template>

<script setup>
/**
 * 单步执行页（策划书 F2 + F3 + F4）
 *
 * 「不吓你」的载体：整屏只显示当前这一步。
 *  - 没有待办列表、没有进度条、没有倒计时、没有下一步预览
 *  - 底部只有「这步做完了」「今天到这吧」
 *  - 点「这步做完了」才出下一步；完成耗时会被回传给后端（自适应粒度的唯一输入）
 *  - 走神 5 分钟：轻轻浮一句「我在这儿，需要了叫我」，最多 2 次
 *  - 点「今天到这吧」直接走，不弹确认、不留记录
 */
import { computed, ref, watch } from 'vue'
import { onHide, onShow, onUnload } from '@dcloudio/uni-app'

import CatBuddy from '@/components/CatBuddy.vue'
import SoftLine from '@/components/SoftLine.vue'

import { useSession } from '@/store/session.js'
import { useSettings } from '@/store/settings.js'
import { useSoftRecall } from '@/composables/useSoftRecall.js'
import FiveMinuteChoice from '@/components/FiveMinuteChoice.vue'
import { catPoseOfSteps } from '@/utils/format.js'
import { getStatusBarHeight } from '@/utils/systemInfo.js'

const session = useSession()
const settings = useSettings()

/** custom 导航栏：自己让出状态栏高度 */
const statusBarStyle = 'height:' + getStatusBarHeight() + 'px;'

const themeClass = computed(() => (settings.sensory ? 'theme-sensory' : ''))

/**
 * 「这一页翻过去了」的落感动效：换一步就换一次动画类名，
 * 两个同名不同 keyframes 的类交替使用，才能真正重播（仅改 keyframe 名不重播）。
 * 感官友好模式下这些动画被全局样式关掉。
 */
const animTick = ref(0)
const animClass = computed(() => 'anim-' + (animTick.value % 2))

/** 只认当前这一步，别的一概不碰 */
const currentStep = computed(() => {
	const task = session.task
	return task && task.current_step ? task.current_step : '先歇一会儿。'
})

const catPose = computed(() => catPoseOfSteps(session.task ? session.task.steps_done : 0))

const {
	text: recallText,
	poke: pokeRecall,
	resume: resumeRecall,
	stop: stopRecall,
	reset: resetRecall
} = useSoftRecall({ enabled: () => !settings.dnd })

let pageVersion = 0

onShow(async () => {
	const version = ++pageVersion
	leaving = false
	settings.load()
	if (!session.task || session.task.state !== 'executing') {
		if (session.state === 'executing') await session.syncState()
		if (version !== pageVersion) return
		if (!session.task || session.task.state !== 'executing') {
			backToChat()
			return
		}
	}
	resetRecall()
})

function stopPageChecks() {
	pageVersion += 1
	stopRecall()
}

onHide(stopPageChecks)
onUnload(stopPageChecks)

function onUserTouch() {
	pokeRecall()
}

/** 换了一步就重播一次很轻的「翻页」动画 */
watch(
	() => (session.task ? session.task.current_step : ''),
	() => {
		animTick.value += 1
		resetRecall()
	}
)

/** 任务没了（完成 / 收尾）就回对话页 */
watch(
	() => session.state,
	(state) => {
		if (state !== 'executing') backToChat()
	}
)

watch(
	() => session.navIntent,
	(intent) => {
		if (!intent) return
		session.takeNavIntent()
		if (intent === 'chat') backToChat()
	}
)

async function onDone() {
	if (session.busy) return
	await session.completeStep()
	// 完成后状态由 watch 处理；若还在执行态就继续显示下一步
}

/** 无惩罚退出：不弹确认、不问理由 */
async function onExit() {
	if (session.busy) return
	await session.exitTask()
}

/** 台阶不对当场调 */
async function onHeavy() {
	if (session.busy) return
	await session.resize('smaller')
}

function toggleDnd() {
	settings.toggleDnd()
	if (settings.dnd) stopRecall()
	else resumeRecall()
}

function collapse() {
	backToChat()
}

/** 回到对话页（兼容「单步页是唯一页面」的情况，用 reLaunch） */
let leaving = false

function backToChat() {
	if (leaving) return
	leaving = true
	stopRecall()
	const pages = getCurrentPages()
	if (pages && pages.length > 1) {
		uni.navigateBack({ delta: 1 })
	} else {
		uni.reLaunch({ url: '/pages/chat/chat' })
	}
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
}

.top-row {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 16rpx 28rpx 0;
}

.tiny-link {
	padding: 8rpx 12rpx;
	font-size: 22rpx;
	color: var(--muted);
}

.stage {
	flex: 1;
	display: flex;
	align-items: center;
	justify-content: center;
	padding: 0 72rpx;
}

.step-line {
	animation: sync-in-a 0.5s ease-out;
}

.step-line.anim-0 {
	animation: sync-in-a 0.5s ease-out;
}

.step-line.anim-1 {
	animation: sync-in-b 0.5s ease-out;
}

.step-text {
	font-size: 56rpx;
	line-height: 1.5;
	letter-spacing: 2rpx;
	color: var(--ink);
	text-align: center;
}

@keyframes sync-in-a {
	from {
		opacity: 0;
		transform: translateY(16rpx);
	}
	to {
		opacity: 1;
		transform: translateY(0);
	}
}

@keyframes sync-in-b {
	from {
		opacity: 0;
		transform: translateY(16rpx);
	}
	to {
		opacity: 1;
		transform: translateY(0);
	}
}

.bottom {
	padding: 0 56rpx calc(40rpx + env(safe-area-inset-bottom));
}

.main-btn {
	height: 96rpx;
	margin-bottom: 20rpx;
	border-radius: 24rpx;
	border: 1rpx solid var(--line);
	background-color: var(--surface);
	display: flex;
	align-items: center;
	justify-content: center;
	font-size: 30rpx;
	color: var(--ink-soft);
	transition: background-color var(--dur) linear;
}

.main-btn.primary {
	border-color: var(--cat);
	background-color: var(--cat);
	color: #fdfaf5;
}

.main-btn-hover {
	opacity: 0.86;
}

.heavy-link {
	padding: 8rpx 0 0;
	text-align: center;
	font-size: 22rpx;
	color: var(--muted);
}

.cat-corner {
	position: fixed;
	right: 28rpx;
	bottom: 360rpx;
	opacity: 0.9;
}
</style>
