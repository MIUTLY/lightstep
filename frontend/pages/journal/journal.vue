<template>
	<view class="page" :class="themeClass">
		<!-- 左侧抽屉（fixed，默认隐藏，DOM 位置不影响布局） -->
		<SideDrawer current="journal" />

		<!-- 顶部一句很轻的说明，不做统计、不做连续天数 -->
		<view class="head">
			<text class="head-text">回执攒在这里，只存在这台设备上。</text>
		</view>

		<!-- ============ 1. 日期轴：可横滑，今天固定在最右 ============ -->
		<view class="axis-wrap">
			<!-- 可滑动部分：只放今天之前的日期（从旧到新，左边更旧） -->
			<scroll-view
				class="axis"
				scroll-x
				:scroll-into-view="axisAnchor"
				:scroll-with-animation="true"
				:show-scrollbar="false"
			>
				<view class="axis-row">
					<view
						v-for="day in pastDates"
						:key="day"
						:id="'day-' + day"
						class="day-chip"
						:class="{ active: day === selectedDate }"
						@tap.stop="selectDate(day)"
					>
						<text class="day-text">{{ dateLabel(day) }}</text>
					</view>
				</view>
			</scroll-view>

			<!-- 固定在右侧的「今天」按钮：不随列表滑走 -->
			<view class="axis-fade"></view>
			<view
				class="today-chip"
				:class="{ active: isToday }"
				@tap.stop="selectDate(todayKey)"
			>
				<text class="day-text">{{ dateLabel(todayKey) }}</text>
				<view class="today-dot"></view>
			</view>
		</view>

		<!-- ============ 2. 半本书：只露右半页，左半页裁在屏幕外 ============ -->
		<view class="book-area">
			<view class="book">
				<!-- 纸张层叠边缘（让书有厚度） -->
				<view class="edge edge-2"></view>
				<view class="edge edge-1"></view>

				<!-- 下一页：翻页时从下面露出来 -->
				<view class="paper paper-under">
					<JournalSheet
						:receipt="nextReceipt"
						:date-text="selectedDateLabel"
					/>
				</view>

				<!-- 当前页：点它翻页 -->
				<view class="paper paper-current" :class="{ flipping: flipping }" @tap="onTapPaper">
					<JournalSheet
						:receipt="currentReceipt"
						:date-text="selectedDateLabel"
						:empty-title="emptyTitle"
						:empty-hint="emptyHint"
						@preview="previewImage"
					/>
					<!-- 书脊：靠屏幕左侧的柔和阴影 -->
					<view class="spine"></view>
					<!-- 翻页时扫过纸面的暗部 -->
					<view class="turn-shade"></view>
				</view>
			</view>

			<!-- 书下方：上一页 / 页码 / 删除这一页 -->
			<view class="book-foot">
				<view class="foot-slot foot-left">
					<text v-if="canGoBack" class="foot-link" @tap.stop="prevPage">‹ 上一页</text>
				</view>
				<text class="foot-mid">{{ pageLabel }}</text>
				<view class="foot-slot foot-right">
					<text v-if="currentReceipt" class="foot-link" @tap.stop="onDelete">删除这页</text>
				</view>
			</view>
		</view>
	</view>
</template>

<script setup>
/**
 * 私人静默手帐（策划书 9.2 后半）· 2026-11-08 改版为「日期轴 + 半本书」
 *
 * 结构：
 *   ① 顶部日期轴：可横滑，最右边永远是今天；点哪天，下面翻到哪天。
 *   ② 半本书：只画打开的书**右半页**，左半页裁在屏幕外；纸面有书脊阴影和层叠边缘。
 *   ③ 回执贴图：用 aspectFit 放在纸面内的照片框里，永远不超出纸页。
 *   ④ 翻页：点纸面 → 当前页从右向左翻走，露出下一张；范围只在本日期自己的回执里。
 *
 * ⚠️ 数据全部在本地（uni storage），一条都不上传：
 *   仓库后端已把 /api/journal* 全部改成 410 detail.code=JOURNAL_CLIENT_ONLY，
 *   存储实现在 utils/localJournal.js。
 *
 * 刻意不做：连续天数、统计、进度条、成就、分享入口。
 */
import { computed, nextTick, ref, watch } from 'vue'
import { onShow } from '@dcloudio/uni-app'

import SideDrawer from '@/components/SideDrawer.vue'
import JournalSheet from '@/components/JournalSheet.vue'
import { useSettings } from '@/store/settings.js'
import { listEntries, removeEntry } from '@/utils/localJournal.js'

const settings = useSettings()
const themeClass = computed(() => (settings.sensory ? 'theme-sensory' : ''))

/* ---------------- 日期工具（全部按本地时区，不走 UTC，避免差一天） ---------------- */

function pad2(n) {
	return n < 10 ? '0' + n : '' + n
}

function todayStr() {
	const d = new Date()
	return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate())
}

function keyToDate(key) {
	const parts = String(key).split('-').map(Number)
	return new Date(parts[0], (parts[1] || 1) - 1, parts[2] || 1)
}

function dateToKey(dt) {
	return dt.getFullYear() + '-' + pad2(dt.getMonth() + 1) + '-' + pad2(dt.getDate())
}

/** 在 key 上前后挪 days 天 */
function shiftKey(key, days) {
	const dt = keyToDate(key)
	dt.setDate(dt.getDate() + days)
	return dateToKey(dt)
}

function dayDiff(fromKey, toKey) {
	return Math.round((keyToDate(toKey).getTime() - keyToDate(fromKey).getTime()) / 86400000)
}

/** '2026-11-08' → '11.08' */
function dateLabel(key) {
	const parts = String(key).split('-')
	if (parts.length !== 3) return key
	return parts[1] + '.' + parts[2]
}

/* ---------------- 数据 ---------------- */

const entries = ref([])

const todayKey = ref(todayStr())

/** 按日期分组；同一天按创建时间正序（翻页 = 从早到晚） */
const byDate = computed(() => {
	const map = {}
	entries.value.forEach((entry) => {
		const day = entry && entry.date ? String(entry.date) : ''
		if (!day) return
		if (!map[day]) map[day] = []
		map[day].push(entry)
	})
	Object.keys(map).forEach((day) => {
		map[day].sort((a, b) => String(a.created_at || '').localeCompare(String(b.created_at || '')))
	})
	return map
})

/** 日期轴至少铺 30 天；有更早回执就往前延，最多 180 天 */
const DAYS_MIN = 30
const DAYS_MAX = 180

const dates = computed(() => {
	const keys = Object.keys(byDate.value)
	let start = shiftKey(todayKey.value, -(DAYS_MIN - 1))
	if (keys.length) {
		const earliest = keys.slice().sort()[0]
		if (earliest < start) start = earliest
	}
	if (dayDiff(start, todayKey.value) + 1 > DAYS_MAX) {
		start = shiftKey(todayKey.value, -(DAYS_MAX - 1))
	}
	const list = []
	let cursor = start
	while (cursor <= todayKey.value && list.length < DAYS_MAX) {
		list.push(cursor)
		cursor = shiftKey(cursor, 1)
	}
	return list
})

/** 可滑动的那一段：今天之前的日期（今天单独钉在最右侧，不参与滚动） */
const pastDates = computed(() => dates.value.filter((day) => day !== todayKey.value))

/* ---------------- 选中日期 & 当天回执 ---------------- */

const selectedDate = ref(todayKey.value)
const axisAnchor = ref('')

const selectedDateLabel = computed(() => dateLabel(selectedDate.value))

const dayReceipts = computed(() => byDate.value[selectedDate.value] || [])

/** 当前翻到第几张（0 起） */
const pageIndex = ref(0)

const currentReceipt = computed(() => dayReceipts.value[pageIndex.value] || null)
const nextReceipt = computed(() => dayReceipts.value[pageIndex.value + 1] || null)

const canGoBack = computed(() => pageIndex.value > 0)

const isToday = computed(() => selectedDate.value === todayKey.value)

const pageLabel = computed(() => {
	if (!dayReceipts.value.length) return '还没有回执'
	return pageIndex.value + 1 + ' / ' + dayReceipts.value.length
})

const emptyTitle = computed(() => (isToday.value ? '今天还没有回执' : '这一天还没有回执'))
const emptyHint = computed(() =>
	isToday.value
		? '专注模式里点「就到这儿吧」，就会攒一张进来。'
		: '翻页在这一天用不了，切回今天看看吧。'
)

/* ---------------- 日期轴滚动 ---------------- */

function scrollAxisTo(day) {
	// 先把 anchor 清空再设，保证「点同一个日期」也能滚回去
	axisAnchor.value = ''
	nextTick(() => {
		axisAnchor.value = 'day-' + day
	})
}

function selectDate(day) {
	if (!day) return
	pageIndex.value = 0
	selectedDate.value = day
	// 今天那颗是钉住的，不需要滚动；历史日期滚到可见位置
	if (day !== todayKey.value) scrollAxisTo(day)
}

/* ---------------- 翻页 ---------------- */

/** 翻页动画时长，必须和 WXSS 里 turn-left 的时长一致 */
const TURN_MS = 420

const flipping = ref(false)
let flipTimer = null

function onTapPaper() {
	if (flipping.value) return
	if (!dayReceipts.value.length) {
		uni.showToast({ title: emptyTitle.value, icon: 'none' })
		return
	}
	if (!nextReceipt.value) {
		uni.showToast({ title: '这一天的回执就这些了', icon: 'none' })
		return
	}
	flipping.value = true
	flipTimer = setTimeout(() => {
		pageIndex.value += 1
		flipping.value = false
		flipTimer = null
	}, TURN_MS)
}

function prevPage() {
	if (flipping.value || pageIndex.value <= 0) return
	pageIndex.value -= 1
}

function previewImage(path) {
	if (path && uni.previewImage) uni.previewImage({ urls: [path], current: path })
}

/* ---------------- 数据加载 / 删除 ---------------- */

function load() {
	entries.value = listEntries()
}

onShow(() => {
	settings.load()
	todayKey.value = todayStr()
	load()
	// 进来默认停在今天
	selectedDate.value = todayKey.value
	pageIndex.value = 0
	scrollAxisTo(todayKey.value)
})

watch(
	() => dayReceipts.value.length,
	(len) => {
		if (pageIndex.value > len - 1) pageIndex.value = Math.max(len - 1, 0)
	}
)

function onDelete() {
	const entry = currentReceipt.value
	if (!entry) return
	// 删掉就是删掉，不问理由（但删数据是不可逆的，给一次确认）
	uni.showModal({
		title: '删掉这一页？',
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
</script>

<style scoped>
.page {
	position: relative;
	display: flex;
	flex-direction: column;
	width: 100%;
	height: 100vh;
	box-sizing: border-box;
	overflow: hidden;
	padding: 12rpx 0 calc(16rpx + env(safe-area-inset-bottom));
	background-color: var(--bg);
	color: var(--ink);
}

.head {
	flex: none;
	padding: 8rpx 28rpx 4rpx;
}

.head-text {
	font-size: 22rpx;
	line-height: 1.4;
	color: var(--muted);
}

/* ---------- 日期轴 ---------- */

.axis-wrap {
	position: relative;
	flex: none;
	width: 100%;
}

.axis {
	width: 100%;
	white-space: nowrap;
	overflow: hidden;
}

/* 右侧留出钉住的「今天」按钮的位置，保证最后一个历史日期能完整滑出来 */
.axis-row {
	display: inline-flex;
	align-items: center;
	padding: 18rpx 178rpx 14rpx 28rpx;
}

.day-chip {
	position: relative;
	flex: none;
	display: flex;
	align-items: center;
	justify-content: center;
	height: 64rpx;
	padding: 0 26rpx;
	margin-right: 14rpx;
	border-radius: 999rpx;
	border: 1rpx solid var(--line);
	background-color: var(--surface);
	transition: background-color var(--dur) linear, color var(--dur) linear;
}

.day-text {
	font-size: 24rpx;
	line-height: 1;
	color: var(--ink-soft);
	letter-spacing: 1rpx;
}

/* 选中态：炭黑底 + 米白字，和「发送」按钮同一套语言 */
.day-chip.active,
.today-chip.active {
	border-color: var(--cat);
	background-color: var(--cat);
}

.day-chip.active .day-text,
.today-chip.active .day-text {
	color: #fdfaf5;
	font-weight: 600;
}

/* 覆盖在滑动区右端的渐隐，避免历史日期从「今天」按钮边缘硬切出来。
   一直铺到屏幕右缘（today-chip 本身不透明，会盖住它），这样连右边那 20rpx 的缝也不会漏出半截日期 */
.axis-fade {
	position: absolute;
	right: 0;
	top: 18rpx;
	bottom: 14rpx;
	width: 180rpx;
	pointer-events: none;
	background-image: linear-gradient(90deg, rgba(245, 240, 232, 0), rgba(245, 240, 232, 1));
}

/* 固定的「今天」按钮：始终停在最右侧，不随日期轴滑走 */
.today-chip {
	position: absolute;
	right: 20rpx;
	top: 18rpx;
	height: 64rpx;
	min-width: 132rpx;
	padding: 0 24rpx;
	box-sizing: border-box;
	display: flex;
	align-items: center;
	justify-content: center;
	border-radius: 999rpx;
	border: 1rpx solid var(--line);
	background-color: var(--surface);
	box-shadow: 0 4rpx 12rpx rgba(96, 76, 48, 0.14);
}

/* 今天：下方一个小圆点，选中时反色 */
.today-dot {
	position: absolute;
	left: 50%;
	bottom: 8rpx;
	width: 6rpx;
	height: 6rpx;
	margin-left: -3rpx;
	border-radius: 50%;
	background-color: var(--accent);
}

.today-chip.active .today-dot {
	background-color: #fdfaf5;
}

/* 感官友好模式：渐隐换成纯白，不能还留着米色 */
.theme-sensory .axis-fade {
	background-image: linear-gradient(90deg, rgba(255, 255, 255, 0), rgba(255, 255, 255, 1));
}

/* ---------- 半本书 ---------- */

.book-area {
	position: relative;
	flex: 1;
	min-height: 0;
	margin-top: 6rpx;
	padding-bottom: 0;
}

.book {
	position: absolute;
	/* 左边故意探出屏幕：只露出书的右半页（左半页被裁掉） */
	left: -18rpx;
	right: 26rpx;
	top: 0;
	bottom: 62rpx;
}

/* 纸张层叠：两层薄边，做出「一叠纸」的厚度感 */
.edge {
	position: absolute;
	border-radius: 0 10rpx 10rpx 0;
}

.edge-1 {
	left: 26rpx;
	right: -10rpx;
	top: 10rpx;
	bottom: -8rpx;
	background-color: #efe7d7;
	box-shadow: 0 8rpx 18rpx rgba(96, 76, 48, 0.1);
}

.edge-2 {
	left: 40rpx;
	right: -18rpx;
	top: 18rpx;
	bottom: -16rpx;
	background-color: #e6dcc8;
	border-radius: 0 12rpx 12rpx 0;
}

/* 纸页本体 */
.paper {
	position: absolute;
	left: 0;
	top: 0;
	right: 0;
	bottom: 0;
	overflow: hidden;
	border-radius: 0 10rpx 10rpx 0;
	/* 米白纸面：#F7F3E8 打底，右侧稍微提亮，边缘压暗，做出纸的层次 */
	background-color: #f7f3e8;
	background-image: linear-gradient(
		100deg,
		rgba(255, 255, 255, 0.55) 0%,
		rgba(255, 255, 255, 0) 22%,
		rgba(255, 255, 255, 0) 82%,
		rgba(196, 178, 148, 0.14) 100%
	);
	/* 外侧投影 + 四边内阴影（纸张边缘的细微层次） */
	box-shadow: 0 18rpx 40rpx rgba(96, 76, 48, 0.18),
		inset 0 0 0 1rpx rgba(196, 178, 148, 0.35),
		inset 0 22rpx 30rpx -22rpx rgba(120, 98, 66, 0.28),
		inset 0 -18rpx 26rpx -20rpx rgba(120, 98, 66, 0.22),
		inset -14rpx 0 24rpx -20rpx rgba(120, 98, 66, 0.25);
}

/* 下一张（翻页时露出来的那张），压在下面 */
.paper-under {
	z-index: 1;
}

/* 当前这一张，点它翻页 */
.paper-current {
	z-index: 2;
}

/* 书脊：贴屏幕左侧的柔和阴影，说明「这是书的右半页」 */
.spine {
	position: absolute;
	left: 0;
	top: 0;
	bottom: 0;
	width: 46rpx;
	pointer-events: none;
	background-image: linear-gradient(
		90deg,
		rgba(110, 88, 58, 0.22) 0%,
		rgba(110, 88, 58, 0.1) 42%,
		rgba(110, 88, 58, 0) 100%
	);
}

/* 翻页时扫过纸面的暗部 */
.turn-shade {
	position: absolute;
	left: 0;
	top: 0;
	right: 0;
	bottom: 0;
	opacity: 0;
	pointer-events: none;
	background-image: linear-gradient(
		90deg,
		rgba(74, 58, 38, 0.26) 0%,
		rgba(74, 58, 38, 0.06) 55%,
		rgba(74, 58, 38, 0) 100%
	);
}

/* 从右向左的翻页：整张纸绕左侧（书脊）掀起、向左扫出 */
@keyframes turn-left {
	0% {
		transform: translateX(0) rotate(0deg) skewY(0deg);
		opacity: 1;
	}
	14% {
		transform: translateX(-1.5%) rotate(-1.4deg) skewY(-0.6deg);
		opacity: 1;
	}
	58% {
		transform: translateX(-58%) rotate(-4.2deg) skewY(-1.6deg);
		opacity: 0.96;
	}
	100% {
		transform: translateX(-104%) rotate(-7deg) skewY(-2.4deg);
		opacity: 0.08;
	}
}

@keyframes shade-sweep {
	0% {
		opacity: 0;
	}
	45% {
		opacity: 0.7;
	}
	100% {
		opacity: 0.12;
	}
}

.paper-current.flipping {
	animation: turn-left 420ms cubic-bezier(0.4, 0.05, 0.62, 0.55) forwards;
	transform-origin: left center;
}

.paper-current.flipping .turn-shade {
	animation: shade-sweep 420ms linear forwards;
}

/* 感官友好模式：不翻纸，直接换页（数据替换在脚本里照常发生） */
.theme-sensory .paper-current.flipping {
	animation: none;
	opacity: 0;
}

.theme-sensory .paper-current.flipping .turn-shade {
	animation: none;
}

/* ---------- 书下方的操作条 ---------- */

.book-foot {
	position: absolute;
	left: 28rpx;
	right: 28rpx;
	bottom: 8rpx;
	height: 48rpx;
	display: flex;
	align-items: center;
	justify-content: space-between;
}

.foot-slot {
	flex: 1;
	display: flex;
	align-items: center;
}

.foot-left {
	justify-content: flex-start;
}

.foot-right {
	justify-content: flex-end;
}

.foot-mid {
	flex: none;
	font-size: 22rpx;
	color: var(--muted);
	letter-spacing: 1rpx;
}

.foot-link {
	font-size: 22rpx;
	color: var(--muted);
	padding: 8rpx 6rpx;
}
</style>
