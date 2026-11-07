<template>
	<view v-if="session.state === 'executing' && session.anchorDue" class="anchor-choice">
		<text class="anchor-copy">五分钟到了。继续一会儿，还是今天到这？</text>
		<view class="anchor-actions">
			<view class="anchor-button" @tap.stop="endNow"><text>今天到这</text></view>
			<view class="anchor-button" @tap.stop="continueForFive"><text>再来5分钟</text></view>
		</view>
	</view>
</template>

<script setup>
import { useSession } from '@/store/session.js'

const session = useSession()

function continueForFive() {
	session.continueFiveMinutes()
}

async function endNow() {
	if (session.busy) return
	// 结束失败时会话仍executing，到期选择保留，不假报结束。
	await session.exitTask()
}
</script>

<style scoped>
.anchor-choice {
	flex: none;
	padding: 12rpx 24rpx 20rpx;
	text-align: center;
}
.anchor-copy {
	font-size: 24rpx;
	color: var(--muted);
}
.anchor-actions {
	display: flex;
	justify-content: center;
	padding-top: 12rpx;
}
.anchor-button {
	margin: 0 10rpx;
	padding: 10rpx 24rpx;
	border-radius: 999rpx;
	border: 1rpx solid var(--line);
	background-color: var(--surface);
	color: var(--ink-soft);
	font-size: 22rpx;
}
</style>
