/* 调试页本地手帐；只有用户主动保存才写入，不调用网络。 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.LightStepLocalJournal = factory();
})(typeof window === "undefined" ? this : window, function () {
  "use strict";

  function create(storage, key) {
    function list() {
      const raw = storage.getItem(key);
      if (raw === null) return [];
      const entries = JSON.parse(raw);
      if (!Array.isArray(entries) || entries.some(e => !e ||
        typeof e.id !== "string" || typeof e.note !== "string" ||
        typeof e.date !== "string" || typeof e.created_at !== "string")) {
        throw new Error("手帐数据格式异常，原数据未被覆盖");
      }
      return entries;
    }

    function add(note) {
      if (typeof note !== "string" || !note.trim()) throw new Error("请先写一句话");
      const entries = list();
      const now = new Date();
      const date = [now.getFullYear(), String(now.getMonth() + 1).padStart(2, "0"),
        String(now.getDate()).padStart(2, "0")].join("-");
      const entry = { id: now.getTime() + "_" + Math.random().toString(36).slice(2),
        date, note, created_at: now.toISOString() };
      storage.setItem(key, JSON.stringify([entry, ...entries]));
      return entry;
    }

    function remove(id) {
      const entries = list();
      storage.setItem(key, JSON.stringify(entries.filter(e => e.id !== id)));
    }

    return { list, add, remove };
  }

  return { create };
});
