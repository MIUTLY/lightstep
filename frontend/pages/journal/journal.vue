<template>
	<view class="page" :class="themeClass">
		<!-- 一句很轻的说明，不做统计、不做连续天数 -->
		<view class="head">
			<text class="muted tiny">回执攒在这里。你想翻就翻，不想翻它就不存在。</text>
		</view>

		<!-- 写一句 -->
		<view class="write-row">
			<input
				class="write-input"
				v-model="note"
				placeholder="写一句今天的…"
				confirm-type="done"
				@confirm="onAdd"
			/>
			<view class="write-btn" @tap.stop="onAdd">
				<text>记下</text>
			</view>
		</view>

		<!-- 列表 -->
		<view v-if="loading" class="empty">
			<text class="muted tiny">翻一翻…</text>
		</view>

		<view v-else-if="!entries.length" class="empty">
			<text class="muted tiny">还没有手帐。</text>
		</view>

		<view v-else class="list">
			<view v-for="entry in entries" :key="entry.id" class="item">
				<view class="item-top">
					<text class="item-date">{{ formatDateCN(entry.date) }}</text>
					<view class="del-btn" @tap.stop="onDelete(entry)">
						<text>删除</text>
					</view>
				</view>

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
 * 对应后端：GET /api/journal、POST /api/journal/add、DELETE /api/journal/{id}
 * 注意：后端在「任务全部完成」和「温柔收尾」时会自动写一条回执进手帐，
 * 所以这里可能已经有条目 —— 前端不重复提交，只负责展示和用户主动补一句。
 *
 * 刻意不做：连续天数、统计、进度条、成就、分享入口。
 */
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'

import { journalAdd, journalDelete, journalList } from '@/api/index.js'
import { useSettings } from '@/store/settings.js'
import { useUser } from '@/store/user.js'
import { formatDateCN } from '@/utils/format.js'

const settings = useSettings()
const user = useUser()

const themeClass = computed(() => (settings.sensory ? 'theme-sensory' : ''))
const entries = ref([])
const note = ref('')
const loading = ref(false)

onShow(() => {
	settings.load()
	load()
})

async function load() {
	loading.value = true
	try {
		const list = await journalList(user.current())
		entries.value = Array.isArray(list) ? list : []
	} catch (e) {
		entries.value = []
	} finally {
		loading.value = false
	}
}

async function onAdd() {
	const text = note.value.trim()
	if (!text) return
	try {
		await journalAdd(user.current(), text)
		note.value = ''
		uni.showToast({ title: '记下了', icon: 'none' })
		load()
	} catch (e) {
		/* request 层已经 toast 过 */
	}
}

function onDelete(entry) {
	// 删掉就是删掉，不问理由
	uni.showModal({
		title: '删掉这条？',
		content: '删了就没有了。',
		confirmText: '删掉',
		cancelText: '留着',
		success: async (res) => {
			if (!res.confirm) return
			try {
				await journalDelete(entry.id, user.current())
				load()
			} catch (e) {
				/* ignore */
			}
		}
	})
}
</script>

<style scoped>
.page {
	min-height: 100vh;
	padding: 24rpx 28rpx 60rpx;
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
