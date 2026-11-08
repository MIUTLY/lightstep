import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import vm from 'node:vm'

const root = fileURLToPath(new URL('../../', import.meta.url))

/** 加载实际模块，只替换平台边界；不安装或冒充微信/Vue编译器。 */
export async function loadFrontend(entry, { mocks = {}, globals = {}, expose = [] } = {}) {
	const context = vm.createContext({ console, setInterval, clearInterval, ...globals })
	const modules = new Map()
	function moduleFor(specifier, parent = root + '/entry.js') {
		const path = specifier.startsWith('@/') ? resolve(root, specifier.slice(2))
			: specifier.startsWith('.') ? resolve(dirname(parent), specifier) : specifier
		if (modules.has(path)) return modules.get(path)
		const mock = mocks[specifier] || mocks[path]
		let module
		if (mock) {
			module = new vm.SyntheticModule(Object.keys(mock), function () {
				for (const [name, value] of Object.entries(mock)) this.setExport(name, value)
			}, { context, identifier: path })
		} else {
			let source = readFileSync(path, 'utf8')
			if (path.endsWith('.vue')) {
                source = source.match(/<script setup>([\s\S]*?)<\/script>/)[1]
                if (path === resolve(root, entry) && expose.length) source += '\nexport { ' + expose.join(',') + ' }\n'
            }
			module = new vm.SourceTextModule(source, { context, identifier: path })
		}
		modules.set(path, module)
		return module
	}
	const module = moduleFor('./' + entry)
	await module.link((specifier, parent) => moduleFor(specifier, parent.identifier))
	await module.evaluate()
	return module.namespace
}

export function deferred() {
	let resolve, reject
	const promise = new Promise((yes, no) => { resolve = yes; reject = no })
	return { promise, resolve, reject }
}

export async function flush() {
	await new Promise(resolve => setImmediate(resolve))
}

export function fakeIntervals() {
	let id = 0
	const callbacks = new Map()
	return {
		setInterval(fn) { callbacks.set(++id, fn); return id },
		clearInterval(key) { callbacks.delete(key) },
		get count() { return callbacks.size },
		async tick() {
			for (const fn of [...callbacks.values()]) void fn()
			await flush()
		}
	}
}
