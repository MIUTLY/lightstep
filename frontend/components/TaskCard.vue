<template>
	<view class="task-card">
		<view class="task-head">
			<text class="task-title">{{ task.title }}</text>
			<text class="chip" :class="'chip-' + task.state">{{ stateLabel(task.state) }}</text>
		</view>

		<view v-if="task.current_step" class="task-step">
			<text class="step-label">这一步</text>
			<text class="step-text">{{ task.current_step }}</text>
		</view>

		<view class="task-meta">
			<text v-if="showMeta">已完成 {{ task.steps_done }} 小步 · 粒度 {{ granularityLabel(task.granularity) }}</text>
		</view>
	</view>
</template>

<script setup>
/**
 * 任务快照卡（渲染后端 Reply.task，字段与后端 TaskView 完全同名）
 *
 * showMeta: 是否显示「已完成 N 小步 · 粒度 X」。
 *   默认只在对话里显示一次；单步执行页不显示（策划书 F2：没有进度条、没有统计）。
 */
import { stateLabel, granularityLabel } from '@/utils/format.js'

defineProps({
	task: { type: Object, required: true },
	showMeta: { type: Boolean, default: true }
})
</script>

<style scoped>
.task-card {
	margin-top: 16rpx;
	padding: 20rpx 24rpx;
	background-color: var(--surface-soft);
	border: 1rpx solid var(--line);
	border-radius: 20rpx;
}

.task-head {
	display: flex;
	align-items: center;
	justify-content: space-between;
}

.task-title {
	flex: 1;
	font-size: 30rpx;
	font-weight: 600;
	color: var(--ink);
}

.chip-ready {
	background-color: var(--accent-soft);
	color: var(--accent-deep);
}

.chip-committing {
	background-color: var(--accent-soft);
	color: var(--accent-deep);
}

.chip-executing {
	background-color: var(--accent-soft);
	color: var(--ok);
}

.chip-done {
	background-color: var(--accent-soft);
	color: var(--ok);
}

.task-step {
	margin-top: 12rpx;
	line-height: 1.5;
}

.step-label {
	display: block;
	font-size: 24rpx;
	color: var(--muted);
}

/* 后端 2026-11-08 起，父任务的 current_step 会把动作明细并进同一字段，
   用换行分隔（「洗衣服\n放入衣物；加洗衣液」）。
   这里必须保留换行，否则明细会被压成一行、看起来像一句错话。 */
.step-text {
	display: block;
	margin-top: 2rpx;
	font-size: 30rpx;
	color: var(--ink);
	white-space: pre-wrap;
}

.task-meta {
	margin-top: 8rpx;
	min-height: 8rpx;
	font-size: 22rpx;
	color: var(--muted);
}
</style>
