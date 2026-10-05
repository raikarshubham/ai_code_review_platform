import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { SAMPLES } from '../samples.js'
import { MONACO_LANGUAGE, monacoLanguage } from './languages.js'

// Language ids registered by the register.js files that monaco.js imports. Read from the files
// themselves, because Monaco needs a browser and these tests run in Node.
const imports = [...readFileSync(new URL('./monaco.js', import.meta.url), 'utf8')
  .matchAll(/'(monaco-editor\/languages\/definitions\/[^']+\/register\.js)'/g)].map((m) => m[1])
const registered = new Set(
  imports.flatMap((path) => {
    const file = readFileSync(new URL(`../../node_modules/${path.replace('monaco-editor/', 'monaco-editor/esm/vs/')}`, import.meta.url), 'utf8')
    return [...file.matchAll(/id: "([^"]+)"/g)].map((m) => m[1])
  }),
)

describe('Monaco language map', () => {
  it('covers every language the app offers', () => {
    expect(Object.keys(MONACO_LANGUAGE).sort()).toEqual(Object.keys(SAMPLES).sort())
  })

  it('only uses Monaco ids that monaco.js actually registers', () => {
    for (const id of Object.values(MONACO_LANGUAGE)) {
      expect(registered, `${id} is not registered`).toContain(id)
    }
  })

  it('falls back to plain text for an unknown id', () => {
    expect(monacoLanguage('cobol')).toBe('plaintext')
  })
})
