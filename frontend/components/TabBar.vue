<template>
	<view class="tabbar">
		<view
			v-for="item in items"
			:key="item.key"
			class="tab-item"
			:class="{ active: item.key === current }"
			:hover-class="item.key === current ? '' : 'tab-hover'"
			:hover-stay-time="60"
			@tap.stop="onTap(item)"
		>
			<text class="tab-label">{{ item.label }}</text>
			<view v-if="item.key === current" class="tab-dot"></view>
		</view>
	</view>
</template>

<script setup>
/**
 * 底部选择栏（三个一级入口：手账 / 对话 / 设置）
 *
 * 为什么用自绘而不用 pages.json 的 tabBar：
 *   1. 原生 tabBar 需要 81×81 的图标资源，我们这套视觉是纯文字 + 极简风格，不需要图标；
 *   2. 原生 tabBar 的选中态只有「文字颜色」一个维度，做不出明显的胶囊高亮；
 *   3. 原生 tabBar 要求页面必须用 switchTab 且不能携带参数，自绘更灵活。
 *
 * 切换方式用 uni.reLaunch：三个页面都是平级的一级入口，reLaunch 会把页面栈清成 1 层，
 * 避免反复切换后栈里堆一长串页面（也顺手避免了「返回」回到上一个 tab 的怪异体验）。
 */
const props = defineProps({
	/** 当前所在的分区：'journal' | 'chat' | 'settings' */
	current: { type: String, default: 'chat' }
})

const items = [
	{ key: 'journal', label: '手账', url: '/pages/journal/journal' },
	{ key: 'chat', label: '对话', url: '/pages/chat/chat' },
	{ key: 'settings', label: '设置', url: '/pages/settings/settings' }
]

function onTap(item) {
	if (item.key === props.current) return
	uni.reLaunch({ url: item.url })
}
</script>

<style scoped>
.tabbar {
	position: fixed;
	left: 0;
	right: 0;
	bottom: 0;
	z-index: 20;
	display: flex;
	align-items: center;
	padding: 12rpx 24rpx calc(12rpx + env(safe-area-inset-bottom));
	background-color: var(--surface);
	border-top: 1rpx solid var(--line);
}

/* 三个按钮等宽 */
.tab-item {
	flex: 1;
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 14rpx 0;
	margin: 0 8rpx;
	border-radius: 20rpx;
	transition: background-color var(--dur) linear;
}

.tab-label {
	font-size: 26rpx;
	line-height: 1.3;
	color: var(--muted);
	transition: color var(--dur) linear;
}

/* 选中态：胶囊浅底 + 深色加粗文字 + 底部小圆点，三重区分 */
.tab-item.active {
	background-color: var(--accent-soft);
}

.tab-item.active .tab-label {
	color: var(--accent-deep);
	font-weight: 600;
}

.tab-dot {
	width: 8rpx;
	height: 8rpx;
	margin-top: 8rpx;
	border-radius: 50%;
	background-color: var(--accent-deep);
}

.tab-hover {
	background-color: var(--surface-soft);
}
</style>
