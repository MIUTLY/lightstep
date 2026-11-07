<template>
	<view class="page" :class="themeClass">
		<!-- 底部选择栏（fixed，DOM 位置不影响定位） -->
		<TabBar current="settings" />

		<!-- 神经友好三件套 -->
		<view class="group">
			<view class="group-title">
				<text class="muted tiny">看得舒服一点</text>
			</view>

			<view class="cell">
				<view class="cell-main">
					<text class="cell-title">感官友好模式</text>
					<text class="cell-sub">降低饱和度、关掉所有动效、纯黑白</text>
				</view>
				<switch
					:checked="settings.sensory"
					:color="switchColor"
					@change="onSensoryChange"
				/>
			</view>

			<view class="cell">
				<view class="cell-main">
					<text class="cell-title">勿扰</text>
					<text class="cell-sub">关掉那两句「我在这儿」，安静陪你</text>
				</view>
				<switch :checked="settings.dnd" :color="switchColor" @change="onDndChange" />
			</view>

			<view class="cell cell-disabled">
				<view class="cell-main">
					<text class="cell-title">显示全部步骤</text>
					<text class="cell-sub">需后端新增接口：目前 /api 只返回当前这一步（current_step），没有完整步骤数组</text>
				</view>
				<switch :checked="false" :disabled="true" :color="switchColor" />
			</view>
		</view>

		<!-- 联调 -->
		<view class="group">
			<view class="group-title">
				<text class="muted tiny">联调</text>
			</view>

			<view class="cell" @tap.stop="editBaseUrl">
				<view class="cell-main">
					<text class="cell-title">后端地址</text>
					<text class="cell-sub">{{ baseUrl }}</text>
				</view>
				<text class="cell-arrow">改</text>
			</view>

			<view class="cell" @tap.stop="onResetIdentity">
				<view class="cell-main">
					<text class="cell-title">换一个人</text>
					<text class="cell-sub">当前身份 {{ shortUserId }}（摩擦地图会重新开始积累）</text>
				</view>
				<text class="cell-arrow">重置</text>
			</view>
		</view>

		<!-- 藏得很深的历史入口：一行很小的灰字 -->
		<view class="deep-link" @tap.stop="goHistory">
			<text>看看之前做了什么</text>
		</view>

		<view class="about">
			<text class="muted tiny">轻步 LightStep · v{{ version }}</text>
			<text class="muted tiny">学习不用急，一步就好。</text>
		</view>
	</view>
</template>

<script setup>
/**
 * 设置页（策划书 F5 + 9.3 历史入口 + 联调开关）
 *
 * 这里刻意只有最少的东西：两个能立刻改变手感的开关、
 * 一个明确标注「待接入」的开关、一个后端地址、一个身份重置，
 * 以及最下面那行藏得很深的小灰字。
 */
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'

import { APP_VERSION } from '@/config/index.js'
import { getBaseUrl, setBaseUrl } from '@/api/request.js'
import TabBar from '@/components/TabBar.vue'
import { useSettings } from '@/store/settings.js'
import { useUser } from '@/store/user.js'

const settings = useSettings()
const user = useUser()

const version = APP_VERSION
const baseUrl = ref('')
const themeClass = computed(() => (settings.sensory ? 'theme-sensory' : ''))
const switchColor = computed(() => (settings.sensory ? '#666666' : '#d9872b'))

const shortUserId = computed(() => {
	const id = user.userId || ''
	return id.length > 12 ? id.slice(0, 6) + '…' + id.slice(-4) : id
})

onShow(() => {
	settings.load()
	user.ensure()
	baseUrl.value = getBaseUrl()
})

function onSensoryChange(e) {
	const next = !!(e && e.detail && e.detail.value)
	if (next !== settings.sensory) settings.toggleSensory()
}

function onDndChange(e) {
	const next = !!(e && e.detail && e.detail.value)
	if (next !== settings.dnd) settings.toggleDnd()
}

/** 改后端地址：真机联调时改成电脑的局域网 IP */
function editBaseUrl() {
	uni.showModal({
		title: '后端地址',
		editable: true,
		placeholderText: 'http://192.168.1.8:8000',
		content: baseUrl.value,
		confirmText: '保存',
		cancelText: '算了',
		success: (res) => {
			if (!res.confirm) return
			const next = String(res.content || '').trim()
			setBaseUrl(next)
			baseUrl.value = getBaseUrl()
			uni.showToast({ title: next ? '改好了' : '已恢复默认', icon: 'none' })
		}
	})
}

function onResetIdentity() {
	uni.showModal({
		title: '换一个人？',
		content: '摩擦地图和跨天交接都跟着当前身份走，换了就重新开始。手帐也看不到了。',
		confirmText: '换',
		cancelText: '不换',
		success: (res) => {
			if (!res.confirm) return
			user.reset()
			uni.showToast({ title: '换好了', icon: 'none' })
		}
	})
}

function goHistory() {
	uni.navigateTo({ url: '/pages/history/history' })
}
</script>

<style scoped>
.page {
	min-height: 100vh;
	/* 底部给固定选择栏让位 */
	padding: 20rpx 28rpx calc(160rpx + env(safe-area-inset-bottom));
	background-color: var(--bg);
	color: var(--ink);
}

.group {
	margin-bottom: 36rpx;
}

.group-title {
	padding: 12rpx 4rpx 12rpx;
}

.cell {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 24rpx 24rpx;
	margin-bottom: 14rpx;
	border-radius: 20rpx;
	border: 1rpx solid var(--line);
	background-color: var(--surface);
}

.cell-disabled {
	opacity: 0.62;
}

.cell-main {
	flex: 1;
	display: flex;
	flex-direction: column;
	padding-right: 20rpx;
}

.cell-title {
	font-size: 30rpx;
	color: var(--ink);
}

.cell-sub {
	margin-top: 6rpx;
	font-size: 22rpx;
	line-height: 1.4;
	color: var(--muted);
}

.cell-arrow {
	flex: none;
	padding: 4rpx 16rpx;
	border-radius: 999rpx;
	border: 1rpx solid var(--line);
	font-size: 22rpx;
	color: var(--muted);
}

.deep-link {
	margin-top: 60rpx;
	text-align: center;
	font-size: 22rpx;
	color: var(--muted);
}

.about {
	margin-top: 24rpx;
	display: flex;
	flex-direction: column;
	align-items: center;
}

.about text {
	margin-bottom: 8rpx;
}
</style>
