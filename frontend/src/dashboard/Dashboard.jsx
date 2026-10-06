// Overview of one analysis: headline numbers, issues by category, function complexity, and this
// browser's recent scores. Plain HTML/CSS bars and one small SVG line, no chart library: the data
// is tiny (5 categories, <= 10 functions, <= 20 points), so a library would only add bundle size.
import { useState } from 'react'
import {
  COMPLEXITY_THRESHOLD,
  SEVERITIES,
  categoryCounts,
  dismissedCount,
  linePoints,
  scoreTrend,
  topFunctions,
} from './data.js'

const formatTime = (iso) => new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })

function StatTile({ label, children }) {
  return (
    <div className="stat-tile">
      <span className="stat-label">{label}</span>
      {children}
    </div>
  )
}

function Kpis({ result }) {
  const counted = result.issues.length - dismissedCount(result.issues)
  const functions = result.functions ?? []
  const maxComplexity = Math.max(0, ...functions.map((f) => f.complexity))
  return (
    <div className="kpis">
      <StatTile label="Score">
        <span className="stat-hero">{result.score}<span className="stat-unit">/100</span></span>
        <span className="meter" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={result.score} aria-label="Score">
          <span style={{ width: `${result.score}%` }} />
        </span>
      </StatTile>
      <StatTile label="Issues">
        <span className="stat-value">{counted}</span>
        <span className="stat-chips">
          {SEVERITIES.filter((s) => result.summary?.[s] > 0).map((s) => (
            <span key={s} className={`severity severity-${s}`} title={`${result.summary[s]} ${s}`}>
              {result.summary[s]} {s}
            </span>
          ))}
        </span>
      </StatTile>
      <StatTile label="Dismissed by AI">
        <span className="stat-value">{dismissedCount(result.issues)}</span>
        <span className="stat-note">false positives, not scored</span>
      </StatTile>
      {functions.length > 0 && (
        <StatTile label="Functions">
          <span className="stat-value">{functions.length}</span>
          <span className="stat-note">most complex: {maxComplexity}</span>
        </StatTile>
      )}
    </div>
  )
}

// One bar row: the label and value are plain text, so the rows read as a table too.
function BarRow({ label, value, max, muted = false, threshold, onClick, tip }) {
  const Tag = onClick ? 'button' : 'div'
  return (
    <Tag className="bar-row" onClick={onClick} tabIndex={onClick ? undefined : 0} data-tip={tip} type={onClick ? 'button' : undefined}>
      <span className="bar-label" title={label}>{label}</span>
      <span className="bar-track">
        {value > 0 && <span className={muted ? 'bar bar-muted' : 'bar'} style={{ width: `${(value / max) * 100}%` }} />}
        {threshold !== undefined && <span className="bar-threshold" style={{ left: `${(threshold / max) * 100}%` }} />}
      </span>
      <span className="bar-value">{value}</span>
    </Tag>
  )
}

function CategoryBars({ issues }) {
  const rows = categoryCounts(issues)
  const max = Math.max(1, ...rows.map((row) => row.count))
  return (
    <section className="chart">
      <h3>Issues by category</h3>
      {rows.map(({ category, count }) => (
        <BarRow key={category} label={category} value={count} max={max}
          tip={`${category}: ${count} issue${count === 1 ? '' : 's'} (false positives not counted)`} />
      ))}
    </section>
  )
}

function ComplexityBars({ functions, onSelect }) {
  const top = topFunctions(functions)
  if (top.length === 0) return null
  // Leave room past the threshold so its marker never sits on the right edge.
  const max = Math.max(COMPLEXITY_THRESHOLD + 2, ...top.map((f) => f.complexity))
  return (
    <section className="chart">
      <h3>Function complexity</h3>
      <p className="chart-note">
        Highest {top.length} of {functions.length}. Above the line ({COMPLEXITY_THRESHOLD}) a function gets hard to
        test and is flagged as an issue. Click a bar to see the function.
      </p>
      {top.map((f) => (
        <BarRow key={`${f.name}-${f.line}`} label={f.name} value={f.complexity} max={max}
          muted={f.complexity <= COMPLEXITY_THRESHOLD} threshold={COMPLEXITY_THRESHOLD}
          onClick={() => onSelect(f)}
          tip={`${f.name} (line ${f.line}): complexity ${f.complexity}${f.complexity > COMPLEXITY_THRESHOLD ? ', above the threshold' : ''}`} />
      ))}
    </section>
  )
}

const W = 320
const H = 120

// Keep the tooltip inside the chart: anchor it to the point's left/right edge near the sides,
// and put it below the point near the top (where it would cover the caption).
function tooltipClass({ x, y }) {
  const align = x < W * 0.25 ? 'tip-left' : x > W * 0.75 ? 'tip-right' : 'tip-center'
  return `chart-tooltip ${align} ${y < H * 0.4 ? 'tip-below' : 'tip-above'}`
}

function ScoreTrend({ historyItems }) {
  const [active, setActive] = useState(null) // index of the hovered/focused point
  const trend = scoreTrend(historyItems)
  if (trend.length < 2) return null
  const points = linePoints(trend.map((t) => t.score), W, H)
  const path = points.map((p, i) => `${i ? 'L' : 'M'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
  const last = trend.length - 1

  return (
    <section className="chart">
      <h3>Recent scores (this browser)</h3>
      <p className="chart-note">
        Your last {trend.length} analyses, oldest to newest. They may be different files, so this is your
        overall trend, not one file's.
      </p>
      <div className="trend" onMouseLeave={() => setActive(null)}>
        <span className="trend-axis trend-axis-top">100</span>
        <span className="trend-axis trend-axis-bottom">0</span>
        <div className="trend-plot">
          <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Scores of the last ${trend.length} analyses, latest ${trend[last].score}`}>
            {[0, 50, 100].map((v) => {
              const y = linePoints([v], W, H)[0].y
              return <line key={v} className="trend-grid" x1="0" x2={W} y1={y} y2={y} />
            })}
            <path className="trend-line" d={path} />
            {points.map((p, i) => (
              <circle key={trend[i].id} className={i === last || i === active ? 'trend-dot trend-dot-strong' : 'trend-dot'}
                cx={p.x} cy={p.y} r={4} />
            ))}
            {/* Bigger invisible hit targets than the 8px dots, also reachable by keyboard. */}
            {points.map((p, i) => (
              <circle key={`hit-${trend[i].id}`} className="trend-hit" cx={p.x} cy={p.y} r={12} tabIndex={0}
                onMouseEnter={() => setActive(i)} onFocus={() => setActive(i)} onBlur={() => setActive(null)}
                aria-label={`${formatTime(trend[i].createdAt)}, ${trend[i].language}, score ${trend[i].score}`} />
            ))}
          </svg>
          {active !== null && (
            <div className={tooltipClass(points[active])} style={{ left: `${(points[active].x / W) * 100}%`, top: `${(points[active].y / H) * 100}%` }}>
              <strong>{trend[active].score}</strong> · {trend[active].language}
              <br />
              {formatTime(trend[active].createdAt)}
            </div>
          )}
        </div>
      </div>
      <details className="chart-table">
        <summary>Show as table</summary>
        <table>
          <thead><tr><th>When</th><th>Language</th><th>Score</th></tr></thead>
          <tbody>
            {[...trend].reverse().map((t) => (
              <tr key={t.id}><td>{formatTime(t.createdAt)}</td><td>{t.language}</td><td>{t.score}</td></tr>
            ))}
          </tbody>
        </table>
      </details>
    </section>
  )
}

export default function Dashboard({ result, historyItems, onSelectFunction }) {
  return (
    <div className="dashboard">
      <Kpis result={result} />
      <CategoryBars issues={result.issues} />
      <ComplexityBars functions={result.functions ?? []} onSelect={onSelectFunction} />
      <ScoreTrend historyItems={historyItems} />
    </div>
  )
}
