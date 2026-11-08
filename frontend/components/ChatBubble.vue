<template>
	<view class="row" :class="'row-' + message.role">
		<!-- 用户说的话 -->
		<view v-if="message.role === 'user'" class="bubble bubble-user">
			<text class="bubble-text user-text">{{ message.text }}</text>
		</view>

		<!-- 系统小字（网络错误之类，不占对话主位） -->
		<view v-else-if="message.role === 'system'" class="sys-note">
			<text>{{ message.text }}</text>
		</view>

		<!-- 小步说的话：完整原图头像（不裁切）放在气泡左侧 -->
		<view v-else class="cat-pair">
			<!-- 完整头像：不做圆形裁切、不缩放裁切，按原比例整只放下（含底下那朵云） -->
			<image class="cat-avatar" src="/static/xiaobu.png" mode="widthFix" />
			<view class="bubble bubble-cat">
			<text v-if="reply" class="bubble-text reply-text">{{ reply }}</text>

			<TaskCard v-if="task" :task="task" />

			<view v-if="summary" class="summary">
				<text>{{ summary }}</text>
			</view>

			<view v-if="reminders.length" class="reminder">
				<text>提醒：{{ reminders.join('、') }}</text>
			</view>

			<ActionBar v-if="buttons.length" :buttons="buttons" @tap="onLabel" />
		</view>
		</view>
	</view>
</template>

<script setup>
/**
 * 一条消息气泡。
 * 后端 Reply 里的 reply / task / summary / due_reminders / buttons 全部原样渲染，
 * 前端不加工文案（语气统一由后端 persona 控制）。
 */
import { computed } from 'vue'
import TaskCard from './TaskCard.vue'
import ActionBar from './ActionBar.vue'

const props = defineProps({
	message: { type: Object, required: true }
})

const emit = defineEmits(['label'])

const reply = computed(() => {
	const r = props.message.reply
	return r && typeof r.reply === 'string' ? r.reply : ''
})

const task = computed(() => {
	const r = props.message.reply
	return r && r.task ? r.task : null
})

const summary = computed(() => {
	const r = props.message.reply
	return r && r.summary ? r.summary : ''
})

const reminders = computed(() => {
	const r = props.message.reply
	return r && Array.isArray(r.due_reminders) ? r.due_reminders : []
})

const buttons = computed(() => {
	const r = props.message.reply
	return r && Array.isArray(r.buttons) ? r.buttons : []
})

function onLabel(label) {
	emit('label', label)
}
</script>

<style scoped>
.row {
	display: flex;
	margin-bottom: 20rpx;
}

.row-user {
	justify-content: flex-end;
}

.row-cat {
	justify-content: flex-start;
}

.row-system {
	justify-content: center;
}

/* 小步的消息：完整头像在左、气泡在右。
   头像不做任何裁切（不用 border-radius / overflow:hidden，也不用 aspectFill），
   直接按原图比例整只显示 —— 素材本身就是"瘫在云上的黑猫"，裁掉云会显得断头断脚。 */
.cat-pair {
	display: flex;
	flex-direction: row;
	align-items: flex-start;
	max-width: 96%;
}

.cat-avatar {
	flex: none;
	/* 完整原图：400×238 的宽幅，宽度定死、高度由 mode="widthFix" 自动。
	   尺寸在 132rpx 的基础上缩到 0.8 倍 → 106rpx（约 105.6rpx）。 */
	width: 106rpx;
	height: auto;
	margin-right: 14rpx;
	margin-top: 4rpx;
}

.bubble {
	max-width: 84%;
	padding: 20rpx 24rpx;
	border-radius: 24rpx;
	font-size: 30rpx;
	word-break: break-all;
}

.bubble-user {
	background-color: var(--cat);
	color: #fdfaf5;
	border-bottom-right-radius: 8rpx;
}

.bubble-cat {
	max-width: 100%;
	background-color: var(--surface);
	border: 1rpx solid var(--line);
	border-bottom-left-radius: 8rpx;
}

.bubble-text {
	display: block;
	line-height: 1.6;
}

.reply-text {
	color: var(--ink);
	white-space: pre-wrap;
}

.user-text {
	color: #fdfaf5;
}

.sys-note {
	padding: 10rpx 20rpx;
	border-radius: 999rpx;
	background-color: var(--accent-soft);
	color: var(--accent-deep);
	font-size: 24rpx;
	text-align: center;
}

.summary {
	margin-top: 14rpx;
	padding-top: 14rpx;
	border-top: 1rpx dashed var(--line);
	color: var(--ok);
	font-size: 24rpx;
	line-height: 1.5;
}

.reminder {
	margin-top: 10rpx;
	font-size: 24rpx;
	color: var(--accent-deep);
}
</style>
