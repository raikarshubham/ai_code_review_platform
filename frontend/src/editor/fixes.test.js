import { describe, expect, it } from 'vitest'
import { applyFix, canApply } from './fixes.js'

const CODE = 'def add_item(item, items=[]):\n    items.append(item)\n    return items\n'
const fix = (fixed_code, fix_start_line, fix_end_line) => ({ fixed_code, fix_start_line, fix_end_line })

describe('applyFix', () => {
  it('replaces a single line', () => {
    expect(applyFix(CODE, fix('    return list(items)', 3, 3)))
      .toBe('def add_item(item, items=[]):\n    items.append(item)\n    return list(items)\n')
  })

  it('replaces several lines with more lines (the line count can change)', () => {
    const fixed = 'def add_item(item, items=None):\n    if items is None:\n        items = []\n    items.append(item)'
    expect(applyFix(CODE, fix(fixed, 1, 2)))
      .toBe('def add_item(item, items=None):\n    if items is None:\n        items = []\n    items.append(item)\n    return items\n')
  })

  it('works on the first and the last line', () => {
    expect(applyFix('a\nb\nc', fix('A', 1, 1))).toBe('A\nb\nc')
    expect(applyFix('a\nb\nc', fix('C', 3, 3))).toBe('a\nb\nC')
  })

  it("keeps the file's CRLF line endings", () => {
    expect(applyFix('a\r\nb\r\nc\r\n', fix('B1\nB2', 2, 2))).toBe('a\r\nB1\r\nB2\r\nc\r\n')
  })

  it('ignores one trailing newline in fixed_code', () => {
    expect(applyFix('a\nb\nc\n', fix('B\n', 2, 2))).toBe('a\nB\nc\n')
  })

  it.each([
    [0, 1], [2, 1], [1, 4], [1.5, 2], [null, 2],
  ])('rejects the bad range %s-%s', (start, end) => {
    expect(() => applyFix('a\nb\nc\n', fix('x', start, end))).toThrow(RangeError)
  })
})

describe('canApply', () => {
  it('needs fixed_code and both line numbers', () => {
    expect(canApply(fix('x', 1, 1))).toBe(true)
    expect(canApply(fix(null, 1, 1))).toBe(false)
    expect(canApply({ fixed_code: 'x', fix_start_line: 1 })).toBe(false)
    expect(canApply(null)).toBe(false)
  })
})
