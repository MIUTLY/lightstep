<template>
	<view class="drawer-root">
		<!-- 左缘箭头：只在收起时出现。
		     展开后**面板右缘不放任何箭头**（按需求），收起靠点遮罩空白处。 -->
		<view
			v-if="!open && edgeHandle"
			class="edge-handle"
			:class="{ 'edge-handle-dim': current !== 'chat' }"
			:hover-class="'edge-hover'"
			:hover-stay-time="60"
			@tap.stop="openDrawer"
		>
			<text class="edge-icon">›</text>
		</view>

		<!-- 遮罩：点侧边栏外部空白处收起（只在打开时存在，不挡正常交互） -->
		<view v-if="open" class="mask" @tap.stop="close"></view>

		<!-- 抽屉本体：position:fixed + translateX(-100%)，收起时完全移出屏幕，
		     **不占页面布局空间** -->
		<view class="panel" :class="{ 'panel-open': open }">
			<!-- 状态栏让位：小程序里 env(safe-area-inset-top) 常取 0，
			     必须用系统给的 statusBarHeight（px）把时间那一行让出来 -->
			<view class="panel-statusbar" :style="'height:' + statusBarHeight + 'px;'"></view>

			<!-- 顶部品牌：点一下回对话 -->
			<view class="panel-brand" @tap.stop="goChat">
				<CatBuddy size="sm" pose="sleep" />
				<view class="brand-text">
					<text class="brand-name">轻步</text>
					<text class="brand-hint">回到对话</text>
				</view>
			</view>

			<view class="menu">
				<view
					v-for="item in items"
					:key="item.key"
					class="menu-item"
					:class="{ active: item.key === current }"
					:hover-class="item.key === current ? '' : 'menu-hover'"
					:hover-stay-time="60"
					@tap.stop="onTap(item)"
				>
					<text class="menu-label">{{ item.label }}</text>
					<text class="menu-hint">{{ item.hint }}</text>
					<view v-if="item.key === current" class="menu-dot"></view>
				</view>
			</view>

			<view class="panel-foot">
				<text class="foot-text">学习不用急，一步就好。</text>
			</view>
		</view>
	</view>
</template>

<script setup>
/**
 * 左侧滑出抽屉（手账 / 备忘录 / 设置）
 *
 * 为什么不用 pages.json 的 tabBar、也不用常驻横向栏：
 *   这套视觉是极简 + 低干扰，常驻栏会一直占着屏幕；
 *   抽屉默认隐藏（fixed + translateX(-100%)，不占布局空间），想切换时才唤出来。
 *
 * 唤出方式（二选一，可同时存在）：
 *   - 页面自己的按钮（对话页右上角三横线）通过 ref 调 open()
 *   - 屏幕左缘的箭头 ›（edgeHandle 开启时；对话页有自己的按钮，传 false）
 *
 * 交互：
 *   - 点左缘箭头 › 展开；展开后**面板右缘不出现任何箭头**，点遮罩空白处收起
 *   - 点「手账」/「备忘录」/「设置」→ uni.reLaunch 切到对应页面
 *   - 点顶部品牌区 → 回对话
 *
 * 页面栈：一级页面之间用 reLaunch 互跳，栈恒为 1 层。
 */
const props = defineProps({
	/** 当前所在页面：'chat' | 'journal' | 'memo' | 'settings' */
	current: { type: String, default: 'chat' },
	/** 是否默认展开（一般用不到，方便调试） */
	defaultOpen: { type: Boolean, default: false },
	/** 收起时是否在屏幕左缘显示箭头按钮 */
	edgeHandle: { type: Boolean, default: true }
})

import { ref } from 'vue'
import CatBuddy from '@/components/CatBuddy.vue'
import { getStatusBarHeight } from '@/utils/systemInfo.js'

const open = ref(props.defaultOpen)

/** custom 导航栏页面里 fixed 元素会顶到屏幕最上方，这里让出状态栏高度（px） */
const statusBarHeight = getStatusBarHeight()

const items = [
	{ key: 'journal', label: '手账', hint: '回执都在这里', url: '/pages/journal/journal' },
	{ key: 'memo', label: '备忘录', hint: '任务时间轴 · 可拖动排序', url: '/pages/memo/memo' },
	{ key: 'settings', label: '设置', hint: '看得舒服一点 · 联调', url: '/pages/settings/settings' }
]

function openDrawer() {
	open.value = true
}

function close() {
	open.value = false
}

function toggle() {
	open.value = !open.value
}

function goChat() {
	close()
	if (props.current === 'chat') return
	uni.reLaunch({ url: '/pages/chat/chat' })
}

function onTap(item) {
	close()
	if (item.key === props.current) return
	uni.reLaunch({ url: item.url })
}

/** 给页面用的开关（对话页右上角三横线按钮通过 ref 调用） */
defineExpose({
	open: openDrawer,
	close,
	toggle
})
</script>

<style scoped>
/* ---------- 左缘箭头（只在收起时出现） ---------- */

.edge-handle {
	position: fixed;
	left: 0;
	top: 38%;
	z-index: 30;
	width: 44rpx;
	height: 96rpx;
	display: flex;
	align-items: center;
	justify-content: center;
	border-radius: 0 20rpx 20rpx 0;
	border: 1rpx solid var(--line);
	border-left: none;
	background-color: var(--surface);
	opacity: 0.92;
}

.edge-handle-dim {
	background-color: var(--surface-soft);
}

.edge-hover {
	background-color: var(--accent-soft);
}

.edge-icon {
	font-size: 30rpx;
	line-height: 1;
	color: var(--muted);
}

/* ---------- 遮罩 ---------- */

.mask {
	position: fixed;
	left: 0;
	right: 0;
	top: 0;
	bottom: 0;
	z-index: 40;
	background-color: rgba(33, 28, 22, 0.18);
}

/* ---------- 抽屉 ---------- */

.panel {
	position: fixed;
	left: 0;
	top: 0;
	bottom: 0;
	z-index: 50;
	width: 470rpx;
	box-sizing: border-box;
	display: flex;
	flex-direction: column;
	padding: 24rpx 24rpx calc(24rpx + env(safe-area-inset-bottom));
	background-color: var(--surface);
	border-right: 1rpx solid var(--line);
	transform: translateX(-100%);
	transition: transform var(--dur) ease;
}

.panel-statusbar {
	flex: none;
	width: 100%;
}

.panel-open {
	transform: translateX(0);
}

/* ---------- 品牌区（点它回对话） ---------- */

.panel-brand {
	display: flex;
	align-items: center;
	padding: 8rpx 8rpx 24rpx;
}

.brand-text {
	margin-left: 14rpx;
	display: flex;
	flex-direction: column;
}

.brand-name {
	font-size: 30rpx;
	font-weight: 600;
	letter-spacing: 2rpx;
	color: var(--ink);
}

.brand-hint {
	margin-top: 2rpx;
	font-size: 20rpx;
	color: var(--muted);
}

/* ---------- 菜单 ---------- */

.menu {
	flex: 1;
	padding-top: 8rpx;
	border-top: 1rpx solid var(--line);
}

.menu-item {
	position: relative;
	display: flex;
	flex-direction: column;
	padding: 22rpx 20rpx;
	margin-top: 12rpx;
	border-radius: 18rpx;
	transition: background-color var(--dur) linear;
}

.menu-item.active {
	background-color: var(--accent-soft);
}

.menu-hover {
	background-color: var(--surface-soft);
}

.menu-label {
	font-size: 30rpx;
	color: var(--ink);
}

.menu-item.active .menu-label {
	color: var(--accent-deep);
	font-weight: 600;
}

.menu-hint {
	margin-top: 4rpx;
	font-size: 20rpx;
	color: var(--muted);
}

.menu-dot {
	position: absolute;
	right: 20rpx;
	top: 50%;
	width: 8rpx;
	height: 8rpx;
	margin-top: -4rpx;
	border-radius: 50%;
	background-color: var(--accent-deep);
}

.panel-foot {
	padding-top: 16rpx;
	border-top: 1rpx solid var(--line);
}

.foot-text {
	font-size: 20rpx;
	color: var(--muted);
}
</style>
