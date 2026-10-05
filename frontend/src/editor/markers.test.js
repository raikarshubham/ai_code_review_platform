import { describe, expect, it } from 'vitest'
import { gutterDots, toMarkers } from './markers.js'

// Stand-ins for monaco.MarkerSeverity and an editor model with 10 lines, each indented by 4.
const SEVERITY = { Hint: 1, Info: 2, Warning: 4, Error: 8 }
const MODEL = { lineCount: 10, firstColumn: () => 5, lastColumn: (line) => 20 + line }

const issue = (extra) => ({ tool: 'pylint', rule_id: 'W0102', severity: 'high', line: 3, end_line: null,
  message: 'Dangerous default', ai: null, ...extra })

describe('toMarkers', () => {
  it('maps our five severities onto Monaco marker levels', () => {
    const levels = ['critical', 'high', 'medium', 'low', 'info']
      .map((severity) => toMarkers([issue({ severity })], SEVERITY, MODEL)[0].severity)
    expect(levels).toEqual([8, 8, 4, 2, 1])
  })

  it('underlines only the first line, from its first real character to its end', () => {
    // A complexity finding spans a whole function; squiggling all of it would bury other markers.
    const [marker] = toMarkers([issue({ line: 3, end_line: 25 })], SEVERITY, MODEL)
    expect(marker).toMatchObject({ startLineNumber: 3, startColumn: 5, endLineNumber: 3, endColumn: 23 })
  })

  it('skips false positives', () => {
    const dismissed = issue({ ai: { verdict: 'false_positive', explanation: 'test fixture' } })
    expect(toMarkers([dismissed], SEVERITY, MODEL)).toEqual([])
  })

  it('puts the AI explanation and fix in the hover text, and tool/rule as the source', () => {
    const [marker] = toMarkers([issue({ ai: { verdict: 'confirmed', explanation: 'Shared list.', fix: 'Use None.' } })],
      SEVERITY, MODEL)
    expect(marker.message).toBe('Dangerous default\n\nAI: Shared list.\n\nFix: Use None.')
    expect([marker.source, marker.code]).toEqual(['pylint', 'W0102'])
  })

  it('drops issues on lines that no longer exist after the code was edited', () => {
    const markers = toMarkers([issue({ line: 12 }), issue({ line: 9, end_line: 14 })], SEVERITY, MODEL)
    expect(markers.map((m) => m.startLineNumber)).toEqual([9])
  })
})

describe('gutterDots', () => {
  it('keeps the most severe issue per line and skips false positives', () => {
    const dots = gutterDots([
      issue({ line: 2, severity: 'low' }),
      issue({ line: 2, severity: 'critical' }),
      issue({ line: 7, severity: 'medium' }),
      issue({ line: 5, severity: 'critical', ai: { verdict: 'false_positive' } }),
    ], 10)
    expect(dots).toEqual([{ line: 2, severity: 'critical' }, { line: 7, severity: 'medium' }])
  })
})
