<template>
	<view class="page" :class="themeClass">
		<!-- 左侧抽屉（fixed，默认隐藏，DOM 位置不影响布局） -->
		<SideDrawer current="settings" />

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

			<view class="cell" @tap.stop="checkHealth">
				<view class="cell-main">
					<text class="cell-title">后端连接</text>
					<text class="cell-sub">{{ healthText }}</text>
				</view>
				<text class="cell-arrow">{{ healthChecking ? '…' : '测' }}</text>
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
import { health } from '@/api/index.js'
import SideDrawer from '@/components/SideDrawer.vue'
import { useSettings } from '@/store/settings.js'
import { useUser } from '@/store/user.js'
import { useToday } from '@/store/today.js'
import { useSession } from '@/store/session.js'
import { clearEntries, listEntries } from '@/utils/localJournal.js'

const settings = useSettings()
const user = useUser()
const today = useToday()
const session = useSession()

const version = APP_VERSION
const baseUrl = ref('')
const themeClass = computed(() => (settings.sensory ? 'theme-sensory' : ''))
const switchColor = computed(() => (settings.sensory ? '#666666' : '#d9872b'))

/** 后端连接状态（新版后端提供 GET /api/health） */
const healthText = ref('还没测过，点右边试试')
const healthChecking = ref(false)

async function checkHealth() {
	if (healthChecking.value) return
	healthChecking.value = true
	try {
		const res = await health()
		const ok = res && (res.status === 'ok' || res.status === 'healthy')
		healthText.value = ok
			? '正常 · 存储 ' + (res.storage || '?') + ' · 回执 ' + (res.receipt_storage || '?')
			: '返回异常：' + JSON.stringify(res)
	} catch (e) {
		healthText.value = '连不上（检查后端是否在跑、地址对不对）'
	} finally {
		healthChecking.value = false
	}
}

const shortUserId = computed(() => {
	const id = user.userId || ''
	return id.length > 12 ? id.slice(0, 6) + '…' + id.slice(-4) : id
})

onShow(() => {
	settings.load()
	user.ensure()
	baseUrl.value = getBaseUrl()
	// 进设置页就顺手探一次，省得用户点
	checkHealth()
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
		content: '会换成一个全新的身份：备忘录、摩擦地图、跨天交接都从零开始，本机手账和想法也会一起清掉。',
		confirmText: '换',
		cancelText: '不换',
		success: (res) => {
			if (!res.confirm) return
			// 1. 换身份（后端按 user_id 隔离，新 id 就是新用户）
			user.reset()
			// 2. 清内存里的旧视图：store 是单例，不清的话页面还显示上一个人的清单；
			//    today.revision 也要归零，否则 apply() 会用 revision 守卫把新用户的空清单挡掉
			today.reset()
			session.reset()
			// 3. 清本地数据：手账回执、事件去重记录、思绪倾倒
			//    清之前先数一下有几条，弹 toast 时把条数报出来 —— 万一没清掉能立刻看出来
			let clearedJournal = 0
			try {
				clearedJournal = listEntries().length
			} catch (e) {
				clearedJournal = 0
			}
			clearEntries()
			today.clearEventCache()
			try {
				uni.removeStorageSync('lightstep_thoughts')
			} catch (e) {
				/* ignore */
			}
			// 清完再读一次确认：还剩下几条（正常应该是 0）
			let leftJournal = 0
			try {
				leftJournal = listEntries().length
			} catch (e) {
				leftJournal = 0
			}
			uni.showToast({
				title: leftJournal
					? `手账没清掉（还剩 ${leftJournal} 条）`
					: clearedJournal
						? `换成新用户了，已清 ${clearedJournal} 条手账`
						: '换成新用户了',
				icon: 'none',
				duration: 2600
			})
			// 4. 回首页重新开始（reLaunch 清空页面栈，避免旧页面残留旧数据）
			setTimeout(() => {
				uni.reLaunch({ url: '/pages/chat/chat' })
			}, 350)
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
	/* 底部没有常驻导航了，只留一点呼吸空间 + 安全区 */
	padding: 20rpx 28rpx calc(48rpx + env(safe-area-inset-bottom));
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
