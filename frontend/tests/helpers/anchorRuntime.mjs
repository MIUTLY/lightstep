import { loadFrontend } from './runtime.mjs'

export function fakeClock() {
	let now = 1000, id = 0
	const jobs = new Map()
	return {
		now: () => now,
		setTimeout(fn, delay) { const key = id++; jobs.set(key, { fn, at: now + delay }); return key },
		clearTimeout(key) { jobs.delete(key) },
		get count() { return jobs.size },
		get callbacks() { return [...jobs.values()].map(j => j.fn) },
		jump(ms) { now += ms },
		advance(ms) {
			const end = now + ms
			while (true) {
				const due = [...jobs.entries()].filter(([, j]) => j.at <= end).sort((a, b) => a[1].at - b[1].at)[0]
				if (!due) break
				now = Math.max(now, due[1].at); jobs.delete(due[0]); due[1].fn()
			}
			now = end
		}
	}
}

export function reply(state = 'executing', step = 's0') {
	return { state, reply: '', due_reminders: [], task: state === 'idle' || state === 'done' ? null : {
		state, title: '写论文', current_step: step, step_id: 'task:' + step,
		steps_done: step === 's0' ? 0 : 1, start_due_at: null
	} }
}

export async function sessionRuntime(overrides = {}) {
	const clock = fakeClock(), calls = [], user = { id: 'user' }
	const api = {
		openSession: async () => reply('ready'), chooseTime: async () => reply('committing'),
		commit: async (_, agree) => reply(agree ? 'executing' : 'ready'),
		stepComplete: async () => reply('executing', 's1'), stepResize: async () => reply('executing', 'smaller'),
		addNote: async () => reply('executing', 'smaller'), chat: async () => reply('ready'),
		exitTask: async () => reply('idle'), sessionState: async () => reply(), ...overrides
	}
	for (const [name, fn] of Object.entries(api)) api[name] = (...args) => { calls.push(name); return fn(...args) }
	const DateClock = class extends Date { static now() { return clock.now() } }
	const { useSession } = await loadFrontend('store/session.js', {
		mocks: {
			vue: { reactive: x => x, ref: value => ({ value }) },
			'./user.js': { useUser: () => ({ current: () => user.id }) }, '@/api/index.js': api
		},
		globals: { Date: DateClock, setTimeout: clock.setTimeout, clearTimeout: clock.clearTimeout }
	})
	const session = useSession()
	async function begin() {
		await session.open(); await session.dispatchLabel('现在开始'); await session.dispatchLabel('行')
	}
	return { session, clock, calls, user, begin }
}
