import { describe, expect, it } from 'vitest'
import { categoryCounts, dismissedCount, linePoints, scoreTrend, topFunctions } from './data.js'

const issue = (category, verdict) => ({ category, ai: verdict ? { verdict } : null })

describe('categoryCounts', () => {
  it('counts every category in a fixed order, zeros included, skipping false positives', () => {
    const issues = [issue('bug'), issue('bug'), issue('security', 'confirmed'), issue('smell', 'false_positive')]
    expect(categoryCounts(issues)).toEqual([
      { category: 'security', count: 1 },
      { category: 'bug', count: 2 },
      { category: 'smell', count: 0 },
      { category: 'complexity', count: 0 },
      { category: 'style', count: 0 },
    ])
    expect(dismissedCount(issues)).toBe(1)
  })
})

describe('topFunctions', () => {
  const fn = (name, complexity, line) => ({ name, complexity, line })

  it('sorts by complexity, then by line, and keeps the top n', () => {
    const top = topFunctions([fn('a', 2, 1), fn('b', 11, 9), fn('c', 11, 4), fn('d', 5, 2)], 3)
    expect(top.map((f) => f.name)).toEqual(['c', 'b', 'd'])
  })

  it('handles missing functions (history saved before the field existed)', () => {
    expect(topFunctions(undefined)).toEqual([])
  })
})

describe('scoreTrend', () => {
  it('takes the newest n and returns them oldest first', () => {
    const items = [5, 4, 3, 2, 1].map((n) => ({ id: n, score: n * 10, createdAt: `t${n}`, language: 'python', code: 'x' }))
    expect(scoreTrend(items, 3)).toEqual([
      { id: 3, score: 30, createdAt: 't3', language: 'python' },
      { id: 4, score: 40, createdAt: 't4', language: 'python' },
      { id: 5, score: 50, createdAt: 't5', language: 'python' },
    ])
  })
})

describe('linePoints', () => {
  it('spreads x evenly and maps 100 to the top, 0 to the bottom', () => {
    expect(linePoints([100, 0], 100, 50, 0)).toEqual([{ x: 0, y: 0 }, { x: 100, y: 50 }])
    expect(linePoints([50, 50, 50], 120, 60, 10).map((p) => p.x)).toEqual([10, 60, 110])
  })
})
