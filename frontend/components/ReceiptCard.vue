<template>
	<view class="ticket">
		<view class="notch notch-l"></view>
		<view class="notch notch-r"></view>

		<text class="eyebrow">轻步 · 今日回执</text>

		<view class="ticket-cat">
			<CatBuddy :pose="pose" size="lg" />
		</view>

		<text class="title">今天到此为止</text>

		<view class="ticket-dash"></view>

		<text class="hint">写给自己的一句话</text>

		<view class="lines">
			<view class="line">
				<text v-if="line" class="line-text">{{ line }}</text>
			</view>
			<view class="line"></view>
			<view class="line"></view>
		</view>

		<text class="date">{{ date }}</text>
	</view>
</template>

<script setup>
/**
 * 今日回执卡片（策划书 F6 / 9.2）
 *
 * 竖版 2:3、奶白纸感、左右票根半圆齿孔；
 * 从上到下：极小页眉 → 小步 → 「今天到此为止」 → 虚线 → 一句空白 → 日期。
 * 没有「恭喜完成」、没有撒花、没有 logo、没有按钮、没有积分。
 *
 * 注意：这里只是**屏幕上**的样式版；保存到相册用的是 utils/receipt.js 里
 * 用 canvas 重画的一版（小程序没法直接截图 DOM）。
 */
import CatBuddy from './CatBuddy.vue'

defineProps({
	/** 小步姿势，随今日步数变化（catPoseOfSteps） */
	pose: { type: String, default: 'sleep' },
	/** 用户写的那一句话（只在第一行横线上显示） */
	line: { type: String, default: '' },
	/** 右下角极小日期 */
	date: { type: String, default: '' }
})
</script>

<style scoped>
.ticket {
	position: relative;
	width: 520rpx;
	height: 780rpx;
	padding: 56rpx 56rpx 40rpx;
	box-sizing: border-box;
	display: flex;
	flex-direction: column;
	align-items: center;
	background-color: #fbf8f2;
	border: 1rpx solid var(--line);
	border-radius: 16rpx;
	transition: background-color var(--dur) linear;
}

/* 票根齿孔：用页面底色挖两个半圆 */
.notch {
	position: absolute;
	top: 50%;
	width: 52rpx;
	height: 52rpx;
	margin-top: -26rpx;
	border-radius: 50%;
	background-color: var(--bg);
}

.notch-l {
	left: -26rpx;
}

.notch-r {
	right: -26rpx;
}

.eyebrow {
	font-size: 20rpx;
	letter-spacing: 4rpx;
	color: var(--muted);
}

.ticket-cat {
	margin-top: 40rpx;
	display: flex;
	justify-content: center;
}

.title {
	margin-top: 36rpx;
	font-size: 46rpx;
	font-weight: 600;
	letter-spacing: 4rpx;
	color: var(--ink);
}

.ticket-dash {
	width: 100%;
	margin-top: 36rpx;
	border-top: 1rpx dashed var(--line);
}

.hint {
	margin-top: 24rpx;
	font-size: 22rpx;
	color: var(--muted);
}

.lines {
	width: 100%;
	margin-top: 16rpx;
}

.line {
	height: 66rpx;
	border-bottom: 1rpx solid var(--line);
	display: flex;
	align-items: center;
	justify-content: center;
}

.line-text {
	font-size: 26rpx;
	color: var(--ink-soft);
}

.date {
	position: absolute;
	right: 40rpx;
	bottom: 28rpx;
	font-size: 20rpx;
	color: var(--muted);
}
</style>
