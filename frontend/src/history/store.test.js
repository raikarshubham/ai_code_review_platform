// fake-indexeddb is a complete in-memory IndexedDB for Node, so these tests run the real store
// code (and the real `idb` wrapper), not a mock of it.
import { IDBFactory } from 'fake-indexeddb'
import 'fake-indexeddb/auto'
import { beforeEach, describe, expect, it } from 'vitest'
import { openHistory, toRecord } from './store.js'

const result = (score) => ({
  language: 'python',
  score,
  summary: { critical: 0, high: 1, medium: 0, low: 0, info: 0 },
  issues: [{ tool: 'pylint', rule_id: 'W0102', line: 1, message: 'Dangerous default value' }],
  ai_review: { enabled: false },
  tool_errors: {},
})

const record = (n) => toRecord(`x = ${n}\n`, 'python', result(n), new Date(Date.UTC(2026, 9, 6, 12, n)))

beforeEach(() => {
  // A brand-new empty IndexedDB per test. idb looks up the global `indexedDB` on every open.
  globalThis.indexedDB = new IDBFactory()
})

describe('toRecord', () => {
  it('keeps the code and result and fills in the list fields', () => {
    const r = toRecord('a = 1\nb = 2\n', 'python', result(80), new Date(Date.UTC(2026, 9, 6)))
    expect(r).toMatchObject({ createdAt: '2026-10-06T00:00:00.000Z', language: 'python', score: 80, lines: 2, issueCount: 1 })
    expect(r.summary.high).toBe(1)
    expect(r.code).toBe('a = 1\nb = 2\n')
    expect(r.result.issues[0].rule_id).toBe('W0102')
  })

  it('counts lines like the backend (no extra line for a trailing newline, CRLF too)', () => {
    expect(toRecord('a\r\nb', 'python', result(1)).lines).toBe(2)
    expect(toRecord('a\n', 'python', result(1)).lines).toBe(1)
    expect(toRecord('', 'python', result(1)).lines).toBe(0)
  })
})

describe('history store', () => {
  it('saves and gets back the full record', async () => {
    const history = await openHistory()
    const id = await history.save(record(1))
    const saved = await history.get(id)
    expect(saved.code).toBe('x = 1\n')
    expect(saved.result.score).toBe(1)
    expect(saved.id).toBe(id)
  })

  it('lists newest first, without the code or result', async () => {
    const history = await openHistory()
    for (const n of [1, 2, 3]) await history.save(record(n))
    const items = await history.list()
    expect(items.map((item) => item.score)).toEqual([3, 2, 1])
    expect(items[0]).not.toHaveProperty('code')
    expect(items[0]).not.toHaveProperty('result')
    expect(items[0]).toMatchObject({ language: 'python', lines: 1, issueCount: 1 })
  })

  it('keeps only the newest maxItems', async () => {
    const history = await openHistory({ maxItems: 3 })
    for (const n of [1, 2, 3, 4, 5]) await history.save(record(n))
    expect((await history.list()).map((item) => item.score)).toEqual([5, 4, 3])
  })

  it('removes one item and clears all', async () => {
    const history = await openHistory()
    const first = await history.save(record(1))
    await history.save(record(2))
    await history.remove(first)
    expect(await history.get(first)).toBeUndefined()
    expect(await history.list()).toHaveLength(1)
    await history.clear()
    expect(await history.list()).toEqual([])
  })

  it('survives reopening (the data is in the database, not in memory)', async () => {
    await (await openHistory()).save(record(7))
    const reopened = await openHistory()
    expect((await reopened.list()).map((item) => item.score)).toEqual([7])
  })
})

describe('when IndexedDB is unavailable', () => {
  it('gives null when there is no IndexedDB at all', async () => {
    globalThis.indexedDB = undefined
    expect(await openHistory()).toBeNull()
  })

  it('gives null when opening throws (blocked storage)', async () => {
    globalThis.indexedDB = { open() { throw new DOMException('blocked', 'SecurityError') } }
    expect(await openHistory()).toBeNull()
  })
})
