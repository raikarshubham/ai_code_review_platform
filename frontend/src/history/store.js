// Analysis history, kept in this browser with IndexedDB. Nothing is stored on the server.
//
// Why IndexedDB and not localStorage: localStorage holds ~5 MB of strings and blocks the page on
// every read and write. One analysis can be 100 kB of code plus its results, and we keep 50.
// IndexedDB is asynchronous, stores objects as they are, and has a far larger quota.
// `idb` is a ~1 kB wrapper that turns IndexedDB's callback events into promises.
import { openDB } from 'idb'

const DB_NAME = 'code-review'
const STORE = 'analyses'
export const MAX_ITEMS = 50

// What the history list needs; the code and full result are only read when an item is opened.
const LIST_FIELDS = ['id', 'createdAt', 'language', 'score', 'lines', 'issueCount', 'summary']

/** A history record for one analysis: the code and the full /analyze result, plus list fields. */
export function toRecord(code, language, result, now = new Date()) {
  return {
    createdAt: now.toISOString(),
    language,
    score: result.score,
    // Same rule as the backend's splitlines(): a trailing newline doesn't start another line.
    lines: code === '' ? 0 : code.replace(/\r?\n$/, '').split(/\r?\n/).length,
    issueCount: result.issues.length,
    summary: result.summary,
    code,
    result,
  }
}

/**
 * Open the history database. Resolves to null when IndexedDB is missing or blocked (some private
 * modes, disabled site data): history is a bonus, so callers just skip it then.
 */
export async function openHistory({ maxItems = MAX_ITEMS } = {}) {
  let db
  try {
    db = await openDB(DB_NAME, 1, {
      upgrade(database) {
        // autoIncrement ids only go up, so "newest first" is simply "highest id first".
        database.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true })
      },
    })
  } catch {
    return null
  }

  return {
    /** Add a record, drop the oldest beyond maxItems, return the new id. One transaction, so a
     *  failure part-way leaves the history as it was. */
    async save(record) {
      const tx = db.transaction(STORE, 'readwrite')
      const id = await tx.store.add(record)
      let extra = (await tx.store.count()) - maxItems
      let cursor = extra > 0 ? await tx.store.openCursor() : null // oldest first
      while (cursor && extra > 0) {
        await cursor.delete()
        extra -= 1
        cursor = await cursor.continue()
      }
      await tx.done
      return id
    },

    /** Newest first, list fields only. */
    async list() {
      const items = []
      let cursor = await db.transaction(STORE).store.openCursor(null, 'prev')
      while (cursor) {
        items.push(Object.fromEntries(LIST_FIELDS.map((field) => [field, cursor.value[field]])))
        cursor = await cursor.continue()
      }
      return items
    },

    get: (id) => db.get(STORE, id),
    remove: (id) => db.delete(STORE, id),
    clear: () => db.clear(STORE),
  }
}
