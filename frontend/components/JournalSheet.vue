<template>
	<view class="sheet">
		<!-- 页眉：日期 + 这张回执走了几小步 -->
		<view class="sheet-head">
			<text class="sheet-date">{{ dateText }}</text>
			<text v-if="receipt && receipt.steps_done" class="sheet-steps">{{ receipt.steps_done }} 小步</text>
		</view>

		<!-- 回执贴图：aspectFit 保证永远落在纸面内，不裁切、不溢出。
		     点纸面是翻页，所以放大看图放在长按上，避免两个手势打架。 -->
		<view v-if="receipt" class="sheet-photo">
			<image
				v-if="receipt.imagePath"
				class="photo"
				:src="receipt.imagePath"
				mode="aspectFit"
				@longpress.stop="onPreview"
			/>
			<view v-else class="photo-missing">
				<text class="photo-missing-text">这一张当时没存图</text>
			</view>
		</view>

		<!-- 页脚手写区：任务名 + 那句私人留言 -->
		<view v-if="receipt && (hasTitles || receipt.note)" class="sheet-meta">
			<text v-if="hasTitles" class="meta-titles">{{ receipt.titles.join('、') }}</text>
			<text v-if="receipt.note" class="meta-note">{{ receipt.note }}</text>
		</view>

		<!-- 空状态：这一天没有回执 -->
		<view v-else-if="!receipt" class="sheet-empty">
			<text class="empty-title">{{ emptyTitle }}</text>
			<text class="empty-hint">{{ emptyHint }}</text>
		</view>
	</view>
</template>

<script setup>
/**
 * 手帐的一页纸（书页内容），由 pages/journal 复用两次：
 * 下层放「翻页后要露出来的下一张」，上层放「当前这张」。
 *
 * 只负责排版，不碰数据：receipt 为空时显示空状态。
 */
import { computed } from 'vue'

const props = defineProps({
	/** 一张回执：{ imagePath, titles, note, steps_done, date } | null */
	receipt: { type: Object, default: null },
	/** 页眉上的日期文案，如 '12.16' */
	dateText: { type: String, default: '' },
	emptyTitle: { type: String, default: '这一天还没有回执' },
	emptyHint: { type: String, default: '专注模式里点「就到这儿吧」，就会攒一张进来。' }
})

const emit = defineEmits(['preview'])

const hasTitles = computed(() => !!(props.receipt && Array.isArray(props.receipt.titles) && props.receipt.titles.length))

function onPreview() {
	if (props.receipt && props.receipt.imagePath) emit('preview', props.receipt.imagePath)
}
</script>

<style scoped>
/* 纸面上的内容层：四周留出装订与页边的呼吸空间 */
.sheet {
	position: absolute;
	left: 0;
	top: 0;
	right: 0;
	bottom: 0;
	display: flex;
	flex-direction: column;
	box-sizing: border-box;
	padding: 36rpx 40rpx 34rpx 56rpx;
}

.sheet-head {
	display: flex;
	align-items: baseline;
	justify-content: space-between;
	flex: none;
}

.sheet-date {
	font-size: 26rpx;
	letter-spacing: 2rpx;
	color: var(--muted);
}

.sheet-steps {
	font-size: 22rpx;
	color: var(--muted);
}

/* 贴图区：吃掉剩余高度，图片只在这个盒子里缩放 */
.sheet-photo {
	flex: 1;
	min-height: 0;
	display: flex;
	align-items: center;
	justify-content: center;
	padding: 18rpx 0;
}

.photo {
	display: block;
	width: 100%;
	height: 100%;
	box-sizing: border-box;
	/* 像一张贴上去的照片：白边 + 一点投影 */
	border: 8rpx solid #ffffff;
	background-color: #ffffff;
	box-shadow: 0 10rpx 26rpx rgba(96, 76, 48, 0.18);
}

.photo-missing {
	width: 100%;
	height: 100%;
	display: flex;
	align-items: center;
	justify-content: center;
	border: 2rpx dashed rgba(150, 135, 112, 0.5);
	border-radius: 8rpx;
}

.photo-missing-text {
	font-size: 24rpx;
	color: var(--muted);
}

.sheet-meta {
	flex: none;
	padding-top: 6rpx;
}

.meta-titles {
	display: block;
	font-size: 28rpx;
	color: var(--ink-soft);
}

.meta-note {
	display: block;
	margin-top: 8rpx;
	font-size: 26rpx;
	color: var(--muted);
	line-height: 1.5;
	white-space: pre-wrap;
}

/* 空状态 */
.sheet-empty {
	flex: 1;
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 0 40rpx;
}

.empty-title {
	font-size: 30rpx;
	color: var(--ink-soft);
	letter-spacing: 1rpx;
}

.empty-hint {
	margin-top: 14rpx;
	width: 70%;
	font-size: 22rpx;
	line-height: 1.6;
	text-align: center;
	color: var(--muted);
}
</style>
