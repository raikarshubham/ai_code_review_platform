// The anonymous id that keeps this browser's analysis history separate from everyone else's.
// No accounts: a random UUID is made once and kept in localStorage. It keeps browsers apart, but
// it isn't a password (anyone who copies it sees that history).

const KEY = 'codeReview.clientId'
let memoryId = null // fallback when storage is blocked (private mode, disabled site data)

// `storage` and `makeId` are parameters so the unit tests can pass fakes (Vitest runs in Node).
export function getClientId(storage = globalThis.localStorage, makeId = () => crypto.randomUUID()) {
  try {
    const saved = storage?.getItem(KEY)
    if (saved) return saved
    const id = memoryId ?? makeId()
    storage?.setItem(KEY, id)
    memoryId = id
    return id
  } catch {
    // Storage threw: keep one id for this page load, so history works until the tab closes.
    memoryId ??= makeId()
    return memoryId
  }
}

export function resetClientIdForTests() {
  memoryId = null
}
