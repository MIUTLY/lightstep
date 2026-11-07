<template>
	<view v-if="text" class="soft-line">
		<text class="soft-text">{{ text }}</text>
	</view>
</template>

<script setup>
/**
 * 温和召回：不是弹窗、不是红字、没有声音，
 * 只是屏幕上轻轻浮起一句话（策划书 F3 / 路演脚本 1:55-2:20）。
 */
defineProps({
	text: { type: String, default: '' }
})
</script>

<style scoped>
.soft-line {
	position: fixed;
	left: 0;
	right: 0;
	bottom: 220rpx;
	display: flex;
	justify-content: center;
	pointer-events: none;
	animation: rise 0.6s ease-out;
}

.soft-text {
	padding: 14rpx 28rpx;
	border-radius: 999rpx;
	background-color: var(--surface);
	border: 1rpx solid var(--line);
	color: var(--ink-soft);
	font-size: 26rpx;
}

@keyframes rise {
	from {
		opacity: 0;
		transform: translateY(12rpx);
	}
	to {
		opacity: 1;
		transform: translateY(0);
	}
}
</style>
