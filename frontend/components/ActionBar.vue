<template>
	<view class="action-bar">
		<view
			v-for="(label, index) in buttons"
			:key="label + index"
			class="action-btn"
			:class="{ primary: index === primaryIndex, small: size === 'small' }"
			:hover-class="'action-hover'"
			:hover-stay-time="60"
			@tap.stop="onTap(label)"
		>
			<text>{{ displayLabel(label) }}</text>
		</view>
	</view>
</template>

<script setup>
/**
 * 按钮行。按钮文案由后端 buttons 数组直接给出（中文标签），
 * 这里只做展示替换与点击上报，不猜语义。
 */
import { displayLabel } from '@/utils/format.js'

defineProps({
	buttons: { type: Array, default: () => [] },
	primaryIndex: { type: Number, default: 0 },
	size: { type: String, default: 'normal' }
})

const emit = defineEmits(['tap'])

function onTap(label) {
	emit('tap', label)
}
</script>

<style scoped>
.action-bar {
	display: flex;
	flex-wrap: wrap;
	margin-top: 18rpx;
}

.action-btn {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	margin: 0 16rpx 12rpx 0;
	padding: 14rpx 28rpx;
	border-radius: 999rpx;
	border: 1rpx solid var(--line);
	background-color: var(--surface);
	color: var(--ink-soft);
	font-size: 26rpx;
	line-height: 1.2;
	transition: border-color var(--dur) linear, background-color var(--dur) linear;
}

.action-btn.primary {
	border-color: var(--accent);
	background-color: var(--accent);
	color: #ffffff;
}

.action-btn.small {
	padding: 10rpx 22rpx;
	font-size: 24rpx;
}

.action-hover {
	border-color: var(--accent);
	color: var(--accent-deep);
}

.primary.action-hover {
	color: #ffffff;
	background-color: var(--accent-deep);
}
</style>
