<template>
	<view class="cat-wrap" :class="['size-' + size, 'pose-' + pose]">
		<view class="cushion"></view>
		<view class="cat-body">
			<view class="ear ear-l"></view>
			<view class="ear ear-r"></view>
			<view class="eye eye-l"></view>
			<view class="eye eye-r"></view>
			<view class="nose"></view>
		</view>
	</view>
</template>

<script setup>
/**
 * 小步（黑猫）。
 *
 * 为什么用纯 CSS 画而不用图片：
 *   1. 小程序（mp-weixin）模板里不支持内联 <svg>，用图片又得带一堆 png 资源；
 *   2. 纯 CSS 才能跟着步数换姿势（策划书 9.2：1 步瘫着 / 3 步坐起 / 5 步伸懒腰），
 *      而且感官友好模式下能一键关掉所有过渡。
 *
 * pose: sleep（瘫着）/ awake（半睁眼）/ sit（坐起来一点）/ stretch（伸懒腰）
 * size: sm（角落 72rpx）/ md（120rpx）/ lg（200rpx）
 */
defineProps({
	pose: { type: String, default: 'sleep' },
	size: { type: String, default: 'md' }
})
</script>

<style scoped>
.cat-wrap {
	position: relative;
	flex: none;
	transition: transform var(--dur) linear;
}

.size-sm {
	width: 72rpx;
	height: 72rpx;
}

.size-md {
	width: 120rpx;
	height: 120rpx;
}

.size-lg {
	width: 200rpx;
	height: 200rpx;
}

/* 半埋着的那块「像沙发又像云」的东西 */
.cushion {
	position: absolute;
	left: 2%;
	right: 2%;
	bottom: 0;
	height: 24%;
	border-radius: 50%;
	background-color: var(--accent-soft);
	transition: background-color var(--dur) linear;
}

.cat-body {
	position: absolute;
	left: 10%;
	right: 10%;
	bottom: 8%;
	height: 72%;
	background-color: var(--cat);
	border-radius: 50% 50% 44% 44% / 58% 58% 42% 42%;
	transition: background-color var(--dur) linear, height var(--dur) linear,
		transform var(--dur) linear;
}

/* 耳朵：上半圆、下半尖的叶片形，向内收着长在头顶两侧 —— 别画成圆熊耳 */
.ear {
	position: absolute;
	top: -20%;
	width: 25%;
	height: 40%;
	background-color: var(--cat);
	border-radius: 76% 14% 76% 14%;
}

.ear-l {
	left: 14%;
	transform: rotate(-12deg);
}

.ear-r {
	right: 14%;
	transform: rotate(12deg);
}

/* 眼睛：半睁的琥珀色，永远不是圆的 */
.eye {
	position: absolute;
	top: 34%;
	width: 20%;
	height: 14%;
	border-radius: 50%;
	background-color: var(--accent);
	transition: height var(--dur) linear, background-color var(--dur) linear;
}

.eye-l {
	left: 22%;
}

.eye-r {
	right: 22%;
}

.nose {
	position: absolute;
	top: 58%;
	left: 46%;
	width: 8%;
	height: 7%;
	background-color: var(--surface);
	border-radius: 50%;
}

/* ---------- 姿势 ---------- */

.pose-sleep .cat-body {
	height: 62%;
	transform: scaleX(1.06) translateY(2%);
}

.pose-sleep .eye {
	height: 5%;
}

.pose-sleep .ear {
	transform: rotate(-4deg);
}

.pose-sleep .ear-r {
	transform: rotate(4deg);
}

.pose-awake .cat-body {
	height: 72%;
}

.pose-awake .eye {
	height: 12%;
}

.pose-sit .cat-body {
	height: 86%;
	border-radius: 46% 46% 40% 40% / 62% 62% 38% 38%;
}

.pose-sit .eye {
	height: 17%;
}

.pose-stretch .cat-body {
	height: 66%;
	transform: scaleX(1.16) rotate(-4deg);
}

.pose-stretch .eye {
	height: 18%;
	border-radius: 50% 50% 50% 50%;
}

.pose-stretch .ear-l {
	transform: rotate(-26deg);
}

.pose-stretch .ear-r {
	transform: rotate(26deg);
}
</style>
