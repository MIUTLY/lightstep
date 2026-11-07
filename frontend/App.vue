<script setup>
/**
 * 应用入口：只做两件冷启动的事 —— 恢复身份、读本地偏好。
 * 页面自己的 onShow 里还会再 load 一次（幂等），保证直接从某个页面进来也不会缺状态。
 */
import { onLaunch } from '@dcloudio/uni-app'
import { useUser } from '@/store/user.js'
import { useSettings } from '@/store/settings.js'

const user = useUser()
const settings = useSettings()

onLaunch(() => {
	user.ensure()
	settings.load()
})
</script>

<style>
/* 轻步 LightStep · 全局设计令牌
   约束（沿用后端 static/style.css）：全站不使用渐变、不使用动效庆祝，
   只用平涂色 + 边框 + 极轻阴影。感官友好模式下换成纯黑白、并关闭动效。
   主色：暖米底 + 炭黑猫 + 琥珀（猫眼）。策划书里提到的「柔和蓝绿色」
   可以作为 --accent 的替换（见 docs/字段映射与联调说明.md）。 */

page {
	--bg: #f5f0e8;
	--surface: #ffffff;
	--surface-soft: #fbf8f2;
	--ink: #2c2824;
	--ink-soft: #5a544c;
	--muted: #958c80;
	--line: #e8e0d2;
	--cat: #211c16;
	--accent: #d9872b;
	--accent-deep: #b96f1b;
	--accent-soft: #f6e7ce;
	--ok: #6e8a63;
	--danger: #b05444;
	--radius: 16px;
	--dur: 0.18s;

	background-color: #f5f0e8;
	color: #2c2824;
	font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB",
		"Microsoft YaHei", sans-serif;
	font-size: 30rpx;
	line-height: 1.6;
	-webkit-font-smoothing: antialiased;
}

/* ---------- 感官友好模式：纯黑白 + 无动效 ---------- */

.theme-sensory {
	--bg: #ffffff;
	--surface: #ffffff;
	--surface-soft: #fafafa;
	--ink: #1a1a1a;
	--ink-soft: #3d3d3d;
	--muted: #8a8a8a;
	--line: #dcdcdc;
	--cat: #111111;
	--accent: #2f2f2f;
	--accent-deep: #1a1a1a;
	--accent-soft: #efefef;
	--ok: #555555;
	--danger: #666666;
	--dur: 0s;
}

/* 感官友好模式：把所有会动的东西关掉。
   ⚠️ 注意：WXSS 不支持 `*` 通配选择器（写了会直接编译报错，整个 app.wxss 失效 → 白屏），
   所以这里必须逐个类名列出来，不能偷懒用通配。 */
.theme-sensory .step-line,
.theme-sensory .soft-line,
.theme-sensory .cat-wrap {
	animation: none !important;
	transition: none !important;
}

/* ---------- 页面骨架 ---------- */

.page-root {
	width: 100%;
	box-sizing: border-box;
	min-height: 100vh;
	background-color: var(--bg);
	color: var(--ink);
	transition: background-color var(--dur) linear;
}

.page-safe {
	flex: none;
	/* 具体高度由页面用 :style 绑定状态栏高度（见 utils/systemInfo.js） */
}

/* ---------- 通用文字 / 按钮 ---------- */

.muted {
	color: var(--muted);
}

.tiny {
	font-size: 22rpx;
	line-height: 1.4;
}

.ghost-btn {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	padding: 14rpx 28rpx;
	border-radius: 999rpx;
	border: 1rpx solid var(--line);
	background-color: var(--surface);
	color: var(--ink-soft);
	font-size: 26rpx;
	line-height: 1.2;
}

.primary-btn {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	padding: 16rpx 32rpx;
	border-radius: 999rpx;
	border: 1rpx solid var(--accent);
	background-color: var(--accent);
	color: #ffffff;
	font-size: 28rpx;
	line-height: 1.2;
}

/* 按下反馈统一走组件的 hover-class（WXSS 对伪类支持不完整，不在这里用 :active） */

.chip {
	display: inline-flex;
	align-items: center;
	padding: 4rpx 16rpx;
	border-radius: 999rpx;
	background-color: var(--accent-soft);
	color: var(--accent-deep);
	font-size: 22rpx;
	line-height: 1.5;
}

.dashed {
	border-top: 1rpx dashed var(--line);
}
</style>
