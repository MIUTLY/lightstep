<template>
	<scroll-view class="quick" scroll-x :show-scrollbar="false">
		<view class="quick-inner">
			<view
				v-for="item in items"
				:key="item.key"
				class="quick-btn"
				:hover-class="'quick-hover'"
				:hover-stay-time="60"
				@tap.stop="onAction(item.key)"
			>
				<text>{{ item.label }}</text>
			</view>
		</view>
	</scroll-view>
</template>

<script setup>
/**
 * 小步能做的「5 件小事」+ 回执入口（策划书 9.1 / F6）。
 * 这里只是把一句话发回后端（走 /api/chat 的意图识别），
 * 唯一例外是「今天到此为止」：回执是前端本地生成的，不打后端。
 */
const emit = defineEmits(['action'])

const items = [
	{ key: 'switch', label: '换件小事' },
	{ key: 'afk', label: '发呆' },
	{ key: 'rest', label: '今天什么都不想干' },
	{ key: 'note', label: '走神记笔记' },
	{ key: 'gentle', label: '温柔收尾' },
	{ key: 'receipt', label: '今天到此为止' }
]

function onAction(key) {
	emit('action', key)
}
</script>

<style scoped>
.quick {
	width: 100%;
	box-sizing: border-box;
	white-space: nowrap;
	overflow-x: auto;
	overflow-y: hidden;
}

.quick-inner {
	display: inline-flex;
	align-items: center;
	padding: 0 24rpx;
}

.quick-btn {
	flex: none;
	margin-right: 14rpx;
	padding: 12rpx 24rpx;
	border-radius: 999rpx;
	border: 1rpx solid var(--line);
	background-color: var(--surface-soft);
	color: var(--ink-soft);
	font-size: 24rpx;
	line-height: 1.2;
	transition: border-color var(--dur) linear, color var(--dur) linear;
}

.quick-hover {
	border-color: var(--accent);
	color: var(--accent-deep);
}
</style>
