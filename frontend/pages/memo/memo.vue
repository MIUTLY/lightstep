<template>
	<view class="page" :class="themeClass">
		<!-- 左侧抽屉：手账 / 备忘录 / 设置 -->
		<SideDrawer current="memo" />

		<view class="head">
			<view class="head-row">
				<text class="head-title">备忘录</text>
				<text v-if="today.revision" class="rev">v{{ today.revision }}</text>
			</view>
			<text class="head-sub">{{ today.reply || '小步会把你今天要做的事排成一张清单。' }}</text>

			<!-- 保留的旧日清单 -->
			<view v-if="today.availableDates.length > 1" class="dates">
				<view
					v-for="d in today.availableDates"
					:key="d"
					class="date-chip"
					:class="{ active: d === today.date }"
					@tap.stop="switchDate(d)"
				>
					<text>{{ formatDateCN(d) }}</text>
				</view>
			</view>
		</view>

		<!-- 专注中：提示继续 -->
		<view v-if="today.hasFocus()" class="focus-banner" @tap.stop="goFocus">
			<text class="focus-text">正在专注：{{ today.focus.title }} · 点这里继续</text>
		</view>

		<view v-if="!today.items.length && !today.busy" class="empty">
			<text class="empty-text">{{ today.allCompleted ? '今天这一页做完了。' : '还没有任务，在上面加一条吧。' }}</text>
		</view>

		<!-- 时间轴：左侧纵向虚线 + 每项一个小圆圈节点 -->
		<view v-else class="timeline">
			<view class="axis"></view>

			<view
				v-for="(item, idx) in today.items"
				:key="item.id"
				class="entry"
				:class="{ dragging: dragIndex === idx, lifting: dragIndex === idx && dragOffset !== 0 }"
				:style="dragIndex === idx ? 'transform: translateY(' + dragOffset + 'px); transition:' + (dragOffset !== 0 ? 'none' : 'transform var(--dur) ease') + '; z-index: 20;' : ''"
				@touchstart.stop="onTouchStart(idx, $event)"
				@touchmove.stop.prevent="onTouchMove(idx, $event)"
				@touchend.stop="onTouchEnd"
				@touchcancel.stop="onTouchEnd"
			>
				<view class="node"></view>
				<view class="card" hover-class="card-hover" @tap.stop="onSelect(item)">
					<view class="card-top">
						<text class="card-index">{{ idx + 1 }}</text>
						<view class="handle">
							<view class="handle-line"></view>
							<view class="handle-line"></view>
							<view class="handle-line"></view>
						</view>
					</view>
					<text class="card-title">{{ item.title }}</text>
					<text v-if="item.scope" class="card-scope">{{ item.scope }}</text>
					<text v-if="item.question" class="card-question">需要补充：{{ item.question }}</text>
					<text v-else-if="!item.scope" class="card-tip">点它开始（小步会先问清范围）</text>
				</view>
			</view>
		</view>

		<view class="foot">
			<text class="foot-text">上下拖动可以调整顺序（会同步到后端）；点一项进入专注。</text>
		</view>
	</view>
</template>

<script setup>
/**
 * 备忘录（今日清单 · 时间轴）
 *
 * 数据全部来自后端 `GET /api/today`，排序也提交给后端
 * （`POST /api/today/command {action:'reorder', date, revision, item_ids}`），
 * 所以换设备/重开也能保持顺序 —— 这一点比之前"只存本地"更符合需求。
 *
 * 交互：
 *   - 拖动排序：先本地重排即时反馈，松手后提交；409（revision 过期）就重新拉一次
 *   - 点一项：action=select → 生成/复用森林 → 进专注模式；若 AI 要先澄清，弹窗补 answer
 *   - 加一条：action=intake（只进清单，不开始专注）
 */
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'

import SideDrawer from '@/components/SideDrawer.vue'
import { useSettings } from '@/store/settings.js'
import { useToday } from '@/store/today.js'
import { formatDateCN } from '@/utils/format.js'

const settings = useSettings()
const today = useToday()

const themeClass = computed(() => (settings.sensory ? 'theme-sensory' : ''))

/**
 * 拖拽状态：
 *   dragIndex  正在被拖的项
 *   dragOffset 相对起手的像素位移（跟手用）
 * 交换发生后把 dragOffset 归零，让 CSS transition 把它滑回落位。
 */
const dragIndex = ref(-1)
const dragOffset = ref(0)
let dragStartY = 0
/** 一条的高度（px），超过它的 0.6 倍就换位 */
const stepPx = uni.upx2px(168)
let dirty = false

onShow(() => {
	settings.load()
	today.load()
})

/* ---------------- 选一项 → 进专注模式 ---------------- */

async function onSelect(item) {
	if (today.busy) return
	if (today.hasFocus() && today.focus.item_id !== item.id) {
		uni.showToast({ title: '先结束当前专注', icon: 'none' })
		return
	}
	const view = await today.select(item.id)
	if (!view) return
	const status = view.operation && view.operation.status
	if (status === 'failed') {
		uni.showToast({
			title: (view.operation.error && view.operation.error.message) || '生成失败，再试一次',
			icon: 'none'
		})
		return
	}
	if (status === 'needs_clarification') {
		// 备忘录里不放任何输入框（需求：手账/备忘录都不允许手动输入），
		// 所以把「小步要问的问题」带到专注模式，由那里的聊天框回答。
		// PR #16 起后端用 clarifications 列出所有待澄清项，问题可能属于**别的**任务，
		// 所以优先取它，而不是当前点的那一项。
		const first = today.firstClarification()
		today.pendingSelect = {
			itemId: (first && first.id) || item.id,
			question: (first && first.question) || view.reply || '还需要补充一点信息'
		}
	}
	goFocus()
}

function goFocus() {
	uni.navigateTo({ url: '/pages/focusmode/focusmode' })
}

async function switchDate(d) {
	await today.load(d === today.todayDate ? undefined : d)
}

/* ---------------- 拖拽排序（跟手 + 落位动画 + 提交后端） ---------------- */

function onTouchStart(idx, e) {
	if (today.busy) return
	dragIndex.value = idx
	dragOffset.value = 0
	const t = (e.touches && e.touches[0]) || (e.changedTouches && e.changedTouches[0])
	dragStartY = t ? t.clientY : 0
	dirty = false
}

function onTouchMove(idx, e) {
	if (dragIndex.value !== idx) return
	const t = (e.touches && e.touches[0]) || (e.changedTouches && e.changedTouches[0])
	if (!t) return
	const dy = t.clientY - dragStartY

	// 1) 先让块跟着手指走（inline style 里位移，不设 transition）
	dragOffset.value = dy

	// 2) 越过半行才换位，避免轻微抖动就乱序
	if (Math.abs(dy) < stepPx * 0.6) return
	const target = idx + (dy > 0 ? 1 : -1)
	if (target < 0 || target > today.items.length - 1) return

	const list = today.items.slice()
	const [moved] = list.splice(idx, 1)
	list.splice(target, 0, moved)
	today.items = list
	dragIndex.value = target

	// 3) 归零位移 → transition 生效，块从手指位置滑到新槽位（落位动画）
	dragOffset.value = 0
	dragStartY = t.clientY
	dirty = true
}

async function onTouchEnd() {
	const wasDirty = dirty
	const wasDragging = dragIndex.value >= 0
	dragOffset.value = 0
	dragIndex.value = -1
	dirty = false
	if (!wasDragging || !wasDirty) return

	const ids = today.items.map((x) => x.id)
	const view = await today.reorder(ids)
	if (!view || (view.operation && view.operation.status !== 'succeeded')) {
		// revision 过期 / 网络失败：以服务端为准重新拉
		await today.load()
		uni.showToast({ title: '顺序没同步上，已刷新', icon: 'none' })
	}
}
</script>

<style scoped>
.page {
	min-height: 100vh;
	padding: 24rpx 28rpx calc(60rpx + env(safe-area-inset-bottom));
	background-color: var(--bg);
	color: var(--ink);
}

.head {
	padding: 8rpx 0 20rpx;
}

.head-row {
	display: flex;
	align-items: baseline;
	justify-content: space-between;
}

.head-title {
	font-size: 34rpx;
	font-weight: 600;
	color: var(--ink);
}

.rev {
	font-size: 20rpx;
	color: var(--muted);
}

.head-sub {
	display: block;
	margin-top: 8rpx;
	font-size: 24rpx;
	line-height: 1.6;
	color: var(--ink-soft);
}

.dates {
	display: flex;
	flex-wrap: wrap;
	margin-top: 14rpx;
}

.date-chip {
	margin: 6rpx 10rpx 0 0;
	padding: 6rpx 18rpx;
	border-radius: 999rpx;
	border: 1rpx solid var(--line);
	background-color: var(--surface);
	font-size: 20rpx;
	color: var(--muted);
}

.date-chip.active {
	border-color: var(--accent);
	background-color: var(--accent-soft);
	color: var(--accent-deep);
}

.focus-banner {
	margin-bottom: 16rpx;
	padding: 16rpx 20rpx;
	border-radius: 18rpx;
	background-color: var(--accent-soft);
}

.focus-text {
	font-size: 24rpx;
	color: var(--accent-deep);
}

.empty {
	padding: 70rpx 0;
}

.empty-text {
	font-size: 26rpx;
	color: var(--muted);
}

/* ---------- 时间轴 ---------- */

.timeline {
	position: relative;
	padding-left: 8rpx;
}

.axis {
	position: absolute;
	left: 24rpx;
	top: 12rpx;
	bottom: 12rpx;
	width: 0;
	border-left: 2rpx dashed var(--line);
}

.entry {
	position: relative;
	display: flex;
	align-items: flex-start;
	padding: 0 0 24rpx 56rpx;
	/* 落位动画：拖拽交换后位移归零，靠这条过渡把块滑回新槽位 */
	transition: transform var(--dur) ease;
}

/* 拖拽中：抬起来一点点，看得出手上拿着东西 */
.entry.dragging {
	opacity: 0.96;
}

.entry.dragging .card {
	box-shadow: 0 12rpx 28rpx rgba(33, 28, 22, 0.12);
}

.node {
	position: absolute;
	left: 16rpx;
	top: 30rpx;
	width: 18rpx;
	height: 18rpx;
	border-radius: 50%;
	background-color: var(--surface);
	border: 3rpx solid var(--accent-soft);
	box-sizing: border-box;
}

.entry.dragging .node {
	border-color: var(--accent);
	background-color: var(--accent);
}

.card {
	flex: 1;
	padding: 20rpx 22rpx;
	border-radius: 20rpx;
	border: 1rpx solid var(--line);
	background-color: var(--surface);
	transition: transform var(--dur) linear, background-color var(--dur) linear;
}

.card-hover {
	background-color: var(--surface-soft);
}

.entry.dragging .card {
	background-color: var(--accent-soft);
	transform: scale(0.985);
}

.card-top {
	display: flex;
	align-items: center;
	justify-content: space-between;
}

.card-index {
	font-size: 20rpx;
	color: var(--muted);
}

.card-title {
	display: block;
	margin-top: 6rpx;
	font-size: 30rpx;
	line-height: 1.5;
	color: var(--ink);
	font-weight: 500;
}

.card-scope {
	display: block;
	margin-top: 8rpx;
	font-size: 22rpx;
	line-height: 1.6;
	color: var(--ink-soft);
}

.card-question {
	display: block;
	margin-top: 8rpx;
	font-size: 22rpx;
	color: var(--accent-deep);
}

.card-tip {
	display: block;
	margin-top: 8rpx;
	font-size: 20rpx;
	color: var(--muted);
}

.handle {
	width: 28rpx;
}

.handle-line {
	height: 2rpx;
	margin: 5rpx 0;
	background-color: var(--line);
}

.foot {
	padding-top: 16rpx;
}

.foot-text {
	font-size: 20rpx;
	line-height: 1.6;
	color: var(--muted);
}
</style>
