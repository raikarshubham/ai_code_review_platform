// Turn analysis issues into Monaco markers (squiggles + hover text) and gutter dots.
// Pure functions: Monaco's MarkerSeverity enum and the model's column lookups are passed in,
// so this is unit-testable without a browser.

// Our 5 severities -> Monaco's 4 marker levels (Error is red, Warning yellow, Info blue).
const MARKER_LEVEL = { critical: 'Error', high: 'Error', medium: 'Warning', low: 'Info', info: 'Hint' }
export const SEVERITY_RANK = { critical: 0, high: 1, medium: 2, low: 3, info: 4 }

const isFalsePositive = (issue) => issue.ai?.verdict === 'false_positive'

function hoverText(issue) {
  const parts = [issue.message]
  if (issue.ai?.explanation) parts.push(`AI: ${issue.ai.explanation}`)
  if (issue.ai?.fix) parts.push(`Fix: ${issue.ai.fix}`)
  return parts.join('\n\n')
}

/**
 * @param issues      issues from /analyze
 * @param severities  monaco.MarkerSeverity
 * @param model       { lineCount, firstColumn(line), lastColumn(line) }, from the editor model
 */
export function toMarkers(issues, severities, model) {
  return issues
    // False positives don't count toward the score, so they get no squiggle either.
    .filter((issue) => !isFalsePositive(issue) && issue.line <= model.lineCount)
    // Only the issue's first line is underlined. A complexity finding spans its whole function,
    // and squiggling 25 lines would bury every other marker inside it. Clicking the issue in the
    // list still selects the full line..end_line range.
    .map((issue) => ({
      severity: severities[MARKER_LEVEL[issue.severity]],
      message: hoverText(issue),
      source: issue.tool,
      code: issue.rule_id,
      startLineNumber: issue.line,
      startColumn: model.firstColumn(issue.line), // skip indentation
      endLineNumber: issue.line,
      endColumn: model.lastColumn(issue.line),
    }))
}

/** One dot per line in the gutter, colored by the most severe issue on that line. */
export function gutterDots(issues, lineCount) {
  const worst = new Map()
  for (const issue of issues) {
    if (isFalsePositive(issue) || issue.line > lineCount) continue
    const current = worst.get(issue.line)
    if (!current || SEVERITY_RANK[issue.severity] < SEVERITY_RANK[current]) worst.set(issue.line, issue.severity)
  }
  return [...worst].map(([line, severity]) => ({ line, severity })).sort((a, b) => a.line - b.line)
}
