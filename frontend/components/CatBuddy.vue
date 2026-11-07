<template>
	<view class="cat-wrap" :class="['size-' + size, 'pose-' + pose]">
		<image class="cat-img" :src="src" mode="widthFix" :draggable="false" />
	</view>
</template>

<script setup>
/**
 * 小步（黑猫）。
 *
 * 资源：static/xiaobu.png —— 400×238、透明底，由设计稿 形象.png 裁掉四周留白后降采样
 * （原图 1536×1429 / 466.8 KB → 56.6 KB），深炭灰猫身 + 奶白淡云，与策划书 9.4 一致。
 *
 * 为什么用 image 而不是继续用 CSS 画：
 *   1. 美术资源已经确定，CSS 画出来的必然不像；
 *   2. 一张 56 KB 的图不会撑大包体，却能让形象完全可控。
 *
 * 姿势（策划书 9.2「小步跟着你醒过来」）：美术目前只给了一张「瘫着」，所以四个姿势
 * 都指向同一张图。以后每个姿势拿到独立素材，只改 POSE_IMAGES 这张映射表即可，
 * 调用方（chat / focus / receipt）一行都不用动。
 *
 * size 只控制宽度，高度按图片比例自动（mode="widthFix"）。
 */
import { computed } from 'vue'

const props = defineProps({
	/** sleep（瘫着）/ awake（半睁眼）/ sit（坐起）/ stretch（伸懒腰） */
	pose: { type: String, default: 'sleep' },
	/** sm 96rpx / md 180rpx / lg 340rpx */
	size: { type: String, default: 'md' }
})

const POSE_IMAGES = {
	sleep: '/static/xiaobu.png',
	awake: '/static/xiaobu.png',
	sit: '/static/xiaobu.png',
	stretch: '/static/xiaobu.png'
}

const src = computed(() => POSE_IMAGES[props.pose] || POSE_IMAGES.sleep)
</script>

<style scoped>
.cat-wrap {
	flex: none;
	display: flex;
	align-items: flex-end;
	justify-content: center;
	transition: opacity var(--dur) linear;
}

.cat-img {
	display: block;
	/* 必须显式给宽度：小程序 <image> 默认 320×240px，
	   不写宽度的话头像会直接撑成 320px 宽，把顶栏顶得极高 */
	width: 100%;
	height: auto;
}

.size-sm {
	width: 96rpx;
}

.size-md {
	width: 180rpx;
}

.size-lg {
	width: 340rpx;
}

/* 首页空状态：小猫站在屏幕正中央，要大一档 */
.size-hero {
	width: 420rpx;
}

/* 姿势只做极轻微的差别，避免「同一张图却假装四个状态」显得假；
   真正的四张素材接上后，这里就不用动了 */
.pose-sleep {
	opacity: 0.96;
}

.pose-awake {
	opacity: 1;
}

.pose-sit {
	opacity: 1;
}

.pose-stretch {
	opacity: 1;
}
</style>
