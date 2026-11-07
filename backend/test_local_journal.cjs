const test = require("node:test");
const assert = require("node:assert/strict");
const { create } = require("./static/local-journal.js");

function memoryStorage() {
  const values = new Map();
  return { getItem: key => values.has(key) ? values.get(key) : null,
    setItem: (key, value) => values.set(key, value) };
}

test("only an explicit add persists a private note; reopening and deleting stay local", () => {
  const storage = memoryStorage();
  const journal = create(storage, "user-a");
  assert.deepEqual(journal.list(), []);
  assert.equal(storage.getItem("user-a"), null);
  const entry = journal.add("原样保存我的话");
  assert.equal(create(storage, "user-a").list()[0].note, "原样保存我的话");
  assert.deepEqual(create(storage, "user-b").list(), []);
  journal.remove(entry.id);
  assert.deepEqual(journal.list(), []);
});

test("corrupt data is reported and preserved instead of silently overwritten", () => {
  const storage = memoryStorage();
  storage.setItem("journal", "corrupt");
  assert.throws(() => create(storage, "journal").add("new note"));
  assert.equal(storage.getItem("journal"), "corrupt");
});

test("storage exhaustion reports failure without pretending to have saved", () => {
  const journal = create({ getItem: () => null,
    setItem: () => { throw new Error("quota exceeded"); } }, "journal");
  assert.throws(() => journal.add("private note"), /quota/);
});
