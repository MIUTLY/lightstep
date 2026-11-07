import { reactive } from 'vue'

/**
 * 极简 store 工厂（形态对齐 Pinia 的 option store）
 *
 * 为什么不用 Pinia：
 *   HBuilderX 3.4+ 的 vue3 编译器里虽然内置了 pinia，但**非 CLI 项目**能否解析到
 *   它取决于 HBuilderX 版本与项目模板，是最容易导致「拿到代码打不开」的一环。
 *   这里用 vue3 自带的 reactive 手写 20 行，零依赖、HBuilderX 直接能跑；
 *   业务代码的写法（useXxx() + store.字段 + store.动作()）与 Pinia 完全一致，
 *   想换回 Pinia 只需要把 defineStore 换成 pinia 的实现（见 README 附录）。
 *
 * 用法：
 *   export const useFoo = defineStore('foo', {
 *     state: () => ({ n: 0 }),
 *     actions: (state) => ({ inc() { state.n += 1 } })
 *   })
 *   const foo = useFoo()   // 单例
 */
export function defineStore(id, options) {
	let instance = null

	function useStore() {
		if (instance) return instance
		const state = reactive(options.state ? options.state() : {})
		const actions = options.actions ? options.actions(state) : {}
		instance = Object.assign(state, actions)
		// 便于调试：store.$id
		Object.defineProperty(instance, '$id', { value: id, enumerable: false })
		return instance
	}

	useStore.$id = id
	return useStore
}
