import { beforeEach, describe, expect, it } from 'vitest'
import { getClientId, resetClientIdForTests } from './clientId.js'

function fakeStorage() {
  const data = new Map()
  return { getItem: (k) => data.get(k) ?? null, setItem: (k, v) => data.set(k, v) }
}

const brokenStorage = {
  getItem() { throw new Error('SecurityError') },
  setItem() { throw new Error('SecurityError') },
}

let counter
const makeId = () => `id-${++counter}`

describe('getClientId', () => {
  beforeEach(() => {
    counter = 0
    resetClientIdForTests()
  })

  it('makes an id once and then reuses it', () => {
    const storage = fakeStorage()
    expect(getClientId(storage, makeId)).toBe('id-1')
    expect(getClientId(storage, makeId)).toBe('id-1')
    expect(storage.getItem('codeReview.clientId')).toBe('id-1')
  })

  it('keeps an id that is already stored', () => {
    const storage = fakeStorage()
    storage.setItem('codeReview.clientId', 'saved-id')
    expect(getClientId(storage, makeId)).toBe('saved-id')
    expect(counter).toBe(0)
  })

  it('still gives one stable id when storage throws', () => {
    expect(getClientId(brokenStorage, makeId)).toBe('id-1')
    expect(getClientId(brokenStorage, makeId)).toBe('id-1')
  })

  it('makes a real UUID by default', () => {
    expect(getClientId(fakeStorage())).toMatch(/^[0-9a-f-]{36}$/)
  })
})
