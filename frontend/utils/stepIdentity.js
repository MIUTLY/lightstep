/** 后端优先提供动作标识；兼容旧后端缺少step_id的情况。 */
export function stepKey(task) {
	if (!task) return ''
	return task.step_id || task.title + '|' + task.current_step
}
