<template>
	<view class="page" :class="themeClass">
		<view class="head">
			<text class="muted tiny">只记做了什么，不记做得怎么样。没有分数、没有统计、没有图表。</text>
		</view>

		<view v-if="loading" class="empty">
			<text class="muted tiny">翻一翻…</text>
		</view>

		<view v-else-if="!items.length" class="empty">
			<text class="muted tiny">还没有记下什么。</text>
		</view>

		<view v-else class="list">
			<view v-for="(item, index) in items" :key="item.date + item.title + index" class="row">
				<text class="row-date">{{ formatDateCN(item.date) }}</text>
				<text class="row-title">{{ item.title }}</text>
			</view>
		</view>
	</view>
</template>

<script setup>
/**
 * 历史（策划书 9.3 末尾「关于历史记录：藏得很深，但你想找就能找到」）
 *
 * 入口在设置页最底下，一行很小的灰色字；首页永远不会出现。
 * 对应后端：GET /api/history → [{ date, title }]（最多 30 条，按日期倒序）
 */
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'

import { historyList } from '@/api/index.js'
import { useSettings } from '@/store/settings.js'
import { useUser } from '@/store/user.js'
import { formatDateCN } from '@/utils/format.js'

const settings = useSettings()
const user = useUser()

const themeClass = computed(() => (settings.sensory ? 'theme-sensory' : ''))
const items = ref([])
const loading = ref(false)

onShow(async () => {
	settings.load()
	loading.value = true
	try {
		const list = await historyList(user.current())
		items.value = Array.isArray(list) ? list : []
	} catch (e) {
		items.value = []
	} finally {
		loading.value = false
	}
})
</script>

<style scoped>
.page {
	min-height: 100vh;
	padding: 24rpx 28rpx 60rpx;
	background-color: var(--bg);
	color: var(--ink);
}

.head {
	padding: 8rpx 0 28rpx;
}

.empty {
	padding: 80rpx 0;
	display: flex;
	justify-content: center;
}

.row {
	display: flex;
	align-items: baseline;
	padding: 20rpx 0;
	border-bottom: 1rpx solid var(--line);
}

.row-date {
	flex: none;
	width: 160rpx;
	font-size: 24rpx;
	color: var(--muted);
}

.row-title {
	flex: 1;
	font-size: 28rpx;
	color: var(--ink-soft);
}
</style>
