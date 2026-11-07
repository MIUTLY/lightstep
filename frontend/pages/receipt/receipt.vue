<template>
	<view class="page-root" :class="themeClass">
		<view class="page-safe" :style="statusBarStyle"></view>

		<view class="top-row">
			<view class="tiny-link" @tap.stop="close">
				<text>关掉</text>
			</view>
		</view>

		<scroll-view class="body" scroll-y>
			<view class="card-wrap">
				<ReceiptCard :pose="pose" :line="line" :date="dateLabel" />
			</view>

			<view class="write-wrap">
				<textarea
					class="write-input"
					v-model="line"
					placeholder="写给自己一句话（不写也行）"
					placeholder-class="ph"
					:maxlength="20"
					:show-confirm-bar="false"
					auto-height
				/>
				<text class="muted tiny">这句只存在这张图上，不会上传。</text>
			</view>

			<view class="actions">
				<view class="primary-btn" hover-class="btn-hover" :hover-stay-time="60" @tap.stop="onSave">
					<text>{{ saving ? '正在存…' : '存到相册' }}</text>
				</view>
				<view class="ghost-btn" hover-class="btn-hover" :hover-stay-time="60" @tap.stop="onArchive">
					<text>攒进手帐</text>
				</view>
			</view>

			<view class="foot">
				<text class="muted tiny">产品不记、不存、不统计。想留就存相册，不想留看完就关。</text>
			</view>
		</scroll-view>

		<!-- 离屏画布：和屏幕上那张票根同版式，用于导出 PNG -->
		<canvas
			canvas-id="receiptCanvas"
			id="receiptCanvas"
			class="hidden-canvas"
			:style="canvasStyle"
		></canvas>
	</view>
</template>

<script setup>
/**
 * 今日回执页（策划书 F6 / 9.2）
 *
 * 交互约定：
 *  - 回执在前端生成，默认什么都不上传（连那句手写的话也不上传）
 *  - 只有用户主动点「攒进手帐」，才会 POST /api/journal/add 存一条
 *  - 「存到相册」用 canvas 重画一份同样排版的图再保存
 * 注意：后端在任务完成 / 温柔收尾时也会自动写回执进手帐，所以手帐里本来就会有条目，
 *       这里不重复写入。
 */
import { computed, getCurrentInstance, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'

import ReceiptCard from '@/components/ReceiptCard.vue'
import { journalAdd } from '@/api/index.js'
import { useSession } from '@/store/session.js'
import { useSettings } from '@/store/settings.js'
import { useUser } from '@/store/user.js'
import { catPoseOfSteps, todayCN } from '@/utils/format.js'
import { getStatusBarHeight } from '@/utils/systemInfo.js'
import { RECEIPT_H, RECEIPT_W, drawReceipt, saveCanvasToAlbum } from '@/utils/receipt.js'

const session = useSession()
const settings = useSettings()
const user = useUser()
const instance = getCurrentInstance()

/** custom 导航栏：自己让出状态栏高度 */
const statusBarStyle = 'height:' + getStatusBarHeight() + 'px;'

const themeClass = computed(() => (settings.sensory ? 'theme-sensory' : ''))
const line = ref('')
const steps = ref(0)
const saving = ref(false)
const dateLabel = todayCN()

/** 姿势跟着今日步数走（1 步瘫着 / 3 步坐起 / 5 步以上伸懒腰） */
const pose = computed(() => catPoseOfSteps(steps.value))

const canvasStyle = 'width:' + RECEIPT_W + 'px;height:' + RECEIPT_H + 'px;position:fixed;left:-2000px;top:0;'

onShow(async () => {
	settings.load()
	user.ensure()
	const summary = await session.fetchTodaySummary()
	if (summary) steps.value = summary.steps_done || 0
	else if (session.task) steps.value = session.task.steps_done || 0
})

async function onSave() {
	if (saving.value) return
	saving.value = true
	try {
		await new Promise((resolve) => {
			const ctx = uni.createCanvasContext('receiptCanvas', instance.proxy)
			drawReceipt(
				ctx,
				{
					steps: steps.value,
					line: line.value,
					date: dateLabel,
					sensory: settings.sensory
				},
				resolve
			)
		})
		await saveCanvasToAlbum('receiptCanvas', instance.proxy)
		uni.showToast({ title: '存进相册了', icon: 'none' })
	} catch (err) {
		uni.showToast({ title: (err && err.message) || '没存成，再试一次', icon: 'none' })
	} finally {
		saving.value = false
	}
}

/** 用户主动攒进手帐（这才会上传） */
async function onArchive() {
	try {
		await journalAdd(user.current(), line.value.trim())
		uni.showToast({ title: '攒进手帐了', icon: 'none' })
	} catch (e) {
		/* request 层已提示 */
	}
}

function close() {
	const pages = getCurrentPages()
	if (pages && pages.length > 1) uni.navigateBack({ delta: 1 })
	else uni.reLaunch({ url: '/pages/chat/chat' })
}
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

.top-row {
	display: flex;
	justify-content: flex-end;
	padding: 16rpx 28rpx 0;
}

.tiny-link {
	padding: 8rpx 12rpx;
	font-size: 22rpx;
	color: var(--muted);
}

.body {
	flex: 1;
	height: 0;
}

.card-wrap {
	display: flex;
	justify-content: center;
	padding: 20rpx 0 28rpx;
}

.write-wrap {
	padding: 0 56rpx;
}

.write-input {
	width: 100%;
	min-height: 88rpx;
	padding: 18rpx 22rpx;
	box-sizing: border-box;
	border-radius: 18rpx;
	border: 1rpx solid var(--line);
	background-color: var(--surface);
	color: var(--ink);
	font-size: 28rpx;
	line-height: 1.5;
}

.ph {
	color: var(--muted);
}

.write-wrap text {
	display: block;
	margin-top: 10rpx;
}

.actions {
	display: flex;
	justify-content: center;
	padding: 32rpx 0 20rpx;
}

.actions .primary-btn {
	margin-right: 18rpx;
}

.btn-hover {
	opacity: 0.86;
}

.foot {
	padding: 0 56rpx 60rpx;
	text-align: center;
}

.hidden-canvas {
	width: 600px;
	height: 900px;
	position: fixed;
	left: -2000px;
	top: 0;
}
</style>
