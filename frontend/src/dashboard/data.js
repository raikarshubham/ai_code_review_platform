// Pure data shaping for the dashboard, kept out of the components so it's unit-tested.

// Fixed order, zeros included: rows never jump around or vanish between analyses.
export const CATEGORIES = ['security', 'bug', 'smell', 'complexity', 'style']
export const SEVERITIES = ['critical', 'high', 'medium', 'low', 'info']

// Same threshold as the backend (Radon/Lizard): above this, a function becomes an issue.
export const COMPLEXITY_THRESHOLD = 10

const isDismissed = (issue) => issue.ai?.verdict === 'false_positive'

/** Issues per category, counting only what the score counts (false positives excluded). */
export function categoryCounts(issues) {
  const counts = Object.fromEntries(CATEGORIES.map((category) => [category, 0]))
  for (const issue of issues) {
    if (!isDismissed(issue) && issue.category in counts) counts[issue.category] += 1
  }
  return CATEGORIES.map((category) => ({ category, count: counts[category] }))
}

export function dismissedCount(issues) {
  return issues.filter(isDismissed).length
}

/** The n most complex functions, most complex first (ties keep file order). */
export function topFunctions(functions = [], n = 10) {
  return [...functions].sort((a, b) => b.complexity - a.complexity || a.line - b.line).slice(0, n)
}

/** The last n history items, oldest -> newest (history lists them newest first). */
export function scoreTrend(historyItems, n = 20) {
  return historyItems.slice(0, n).reverse().map(({ id, score, createdAt, language }) => ({ id, score, createdAt, language }))
}

/**
 * SVG coordinates for scores on a fixed 0-100 y scale (a fixed scale, so a dip from 90 to 85
 * doesn't look like a crash). `pad` keeps the end dots inside the viewBox.
 */
export function linePoints(scores, width, height, pad = 8) {
  const step = scores.length > 1 ? (width - 2 * pad) / (scores.length - 1) : 0
  return scores.map((score, i) => ({
    x: pad + i * step,
    y: pad + (1 - score / 100) * (height - 2 * pad),
  }))
}
