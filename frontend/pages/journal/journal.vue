<template>
	<view class="page" :class="themeClass">
		<!-- 左侧抽屉（fixed，默认隐藏，DOM 位置不影响布局） -->
		<SideDrawer current="journal" />

		<!-- 一句很轻的说明，不做统计、不做连续天数 -->
		<view class="head">
			<text class="muted tiny">回执攒在这里，只存在这台设备上。你想翻就翻，不想翻它就不存在。</text>
		</view>

		<!-- 列表 -->
		<view v-if="!entries.length" class="empty">
			<text class="muted tiny">还没有手帐。专注模式里点「就到这吧」会自动攒一张进来。</text>
		</view>

		<view v-else class="list">
			<view v-for="entry in entries" :key="entry.id" class="item">
				<view class="item-top">
					<text class="item-date">{{ formatDateCN(entry.date) }}</text>
					<view class="del-btn" @tap.stop="onDelete(entry)">
						<text>删除</text>
					</view>
				</view>

				<!-- 回执图（只有用户在回执页选过「存到本地」才有） -->
				<image
					v-if="entry.imagePath"
					class="item-image"
					:src="entry.imagePath"
					mode="widthFix"
					@tap.stop="previewImage(entry.imagePath)"
				/>

				<view v-if="entry.titles && entry.titles.length" class="item-titles">
					<text>{{ entry.titles.join('、') }}</text>
				</view>

				<view class="item-steps">
					<text>{{ entry.steps_done }} 小步</text>
				</view>

				<view v-if="entry.note" class="item-note">
					<text>{{ entry.note }}</text>
				</view>
			</view>
		</view>
	</view>
</template>

<script setup>
/**
 * 私人静默手帐（策划书 9.2 后半）
 *
 * ⚠️ 数据全部在本地（uni storage），一条都不上传：
 *   仓库后端已把 /api/journal* 全部改成 410 detail.code=JOURNAL_CLIENT_ONLY，
 *   并在 docs/api.md 写明「回执图片和私人留言仅在客户端保存」。
 *   存储实现在 utils/localJournal.js。
 *
 * 条目里的 steps_done / titles 来自 GET /api/daily/summary（这两个字段是后端算的，
 * 只读、只是拿来把回执写得像一张票根，不构成统计）。
 *
 * 刻意不做：连续天数、统计、进度条、成就、分享入口。
 */
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'

import SideDrawer from '@/components/SideDrawer.vue'
import { useSettings } from '@/store/settings.js'
import { listEntries, removeEntry } from '@/utils/localJournal.js'
import { formatDateCN } from '@/utils/format.js'

const settings = useSettings()

const themeClass = computed(() => (settings.sensory ? 'theme-sensory' : ''))
const entries = ref([])

onShow(() => {
	settings.load()
	load()
})

function load() {
	entries.value = listEntries()
}

function onDelete(entry) {
	// 删掉就是删掉，不问理由（但删数据是不可逆的，给一次确认）
	uni.showModal({
		title: '删掉这条？',
		content: '删了就没有了。',
		confirmText: '删掉',
		cancelText: '留着',
		success: (res) => {
			if (!res.confirm) return
			removeEntry(entry.id)
			load()
		}
	})
}

function previewImage(path) {
	if (uni.previewImage) uni.previewImage({ urls: [path], current: path })
}
</script>

<style scoped>
.page {
	min-height: 100vh;
	/* 底部没有常驻导航了，只留一点呼吸空间 + 安全区 */
	padding: 24rpx 28rpx calc(40rpx + env(safe-area-inset-bottom));
	background-color: var(--bg);
	color: var(--ink);
}

.head {
	padding: 8rpx 0 24rpx;
}

.write-row {
	display: flex;
	align-items: center;
	margin-bottom: 28rpx;
}

.write-input {
	flex: 1;
	height: 80rpx;
	padding: 0 22rpx;
	border-radius: 18rpx;
	border: 1rpx solid var(--line);
	background-color: var(--surface);
	color: var(--ink);
	font-size: 28rpx;
}

.write-btn {
	flex: none;
	margin-left: 14rpx;
	height: 80rpx;
	padding: 0 28rpx;
	border-radius: 18rpx;
	display: flex;
	align-items: center;
	justify-content: center;
	background-color: var(--accent);
	color: #ffffff;
	font-size: 28rpx;
}

.empty {
	padding: 80rpx 0;
	display: flex;
	justify-content: center;
}

.item {
	padding: 24rpx 0;
	border-bottom: 1rpx solid var(--line);
}

.item-top {
	display: flex;
	align-items: center;
	justify-content: space-between;
}

.item-date {
	font-size: 24rpx;
	color: var(--muted);
}

.del-btn {
	padding: 4rpx 18rpx;
	border-radius: 999rpx;
	border: 1rpx solid var(--line);
	font-size: 22rpx;
	color: var(--muted);
}

.item-image {
	display: block;
	width: 320rpx;
	margin-top: 16rpx;
	border-radius: 12rpx;
	border: 1rpx solid var(--line);
}

.item-titles {
	margin-top: 10rpx;
	font-size: 30rpx;
	font-weight: 500;
	color: var(--ink);
}

.item-steps {
	margin-top: 4rpx;
	font-size: 22rpx;
	color: var(--muted);
}

.item-note {
	margin-top: 10rpx;
	font-size: 28rpx;
	color: var(--ink-soft);
}
</style>
