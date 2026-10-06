import { lazy, Suspense, useEffect, useState } from 'react'
import { analyzeCode, checkHealth, getLanguages } from './api.js'
import { canApply } from './editor/fixes.js'
import { SAMPLES } from './samples.js'
import './App.css'

// Monaco is large, so it loads in its own chunk after the page shell is on screen.
const CodeEditor = lazy(() => import('./editor/CodeEditor.jsx'))
const FixDiff = lazy(() => import('./editor/FixDiff.jsx'))

const DEFAULT_LANGUAGE = 'python'
const NO_ISSUES = [] // a stable empty list, so the editor doesn't redo its markers every render

// Used only if GET /languages fails, so the page stays usable (the badge shows the API is down).
const FALLBACK_LANGUAGES = Object.keys(SAMPLES).map((id) => ({ id, label: id }))

function HealthBadge() {
  // 'checking' | 'ok' | 'down'
  const [status, setStatus] = useState('checking')

  useEffect(() => {
    checkHealth()
      .then(() => setStatus('ok'))
      .catch(() => setStatus('down'))
  }, [])

  return <span className={`badge badge-${status}`}>API: {status}</span>
}

function IssueList({ issues, onSelect, onShowFix, stale }) {
  if (issues.length === 0) return <p className="muted">No issues found.</p>

  return (
    <ul className="issues">
      {issues.map((issue, index) => {
        const falsePositive = issue.ai?.verdict === 'false_positive'
        return (
          <li
            key={`${issue.tool}-${issue.rule_id}-${issue.line}-${index}`}
            className={falsePositive ? 'issue issue-dismissed' : 'issue'}
          >
            <span className={`severity severity-${issue.severity}`}>{issue.severity}</span>
            <button className="line" onClick={() => onSelect(issue)} title="Show in editor">
              Line {issue.line}
            </button>
            <span className="message">
              {issue.message}
              {falsePositive && <span className="tag">false positive (not scored)</span>}
              {issue.tool === 'ai' && <span className="tag tag-ai">found by AI</span>}
            </span>
            <span className="meta">
              {issue.tool} · {issue.rule_id} · {issue.category}
            </span>
            {issue.ai && <AINote note={issue.ai} onShowFix={() => onShowFix(issue)} stale={stale} />}
          </li>
        )
      })}
    </ul>
  )
}

// Plain text rendering on purpose: everything here came from the LLM, so it is never
// injected as HTML.
function AINote({ note, onShowFix, stale }) {
  return (
    <div className="ai-note">
      <p>{note.explanation}</p>
      {note.fix && (
        <p>
          <strong>Fix:</strong> {note.fix}
        </p>
      )}
      {canApply(note) && (
        <button
          className="show-fix"
          onClick={onShowFix}
          disabled={stale}
          // A fix's line numbers belong to the analyzed code; after an edit they could point at
          // the wrong lines, so the diff is only offered for up-to-date results.
          title={stale ? 'Re-analyze first: the code changed since this fix was suggested' : undefined}
        >
          Show fix (lines {note.fix_start_line}–{note.fix_end_line})
        </button>
      )}
    </div>
  )
}

function AIStatus({ review }) {
  if (!review?.enabled) return null
  // chunks === 0 means no part of the file was reviewed; otherwise some chunks may have failed.
  if (review.error && !review.chunks) {
    return (
      <div className="warning" role="status">
        <strong>AI review unavailable, showing static analysis only:</strong> {review.error}
      </div>
    )
  }
  return (
    <>
      {review.error && (
        <div className="warning" role="status">
          <strong>AI review incomplete:</strong> {review.error}
        </div>
      )}
      {review.truncated && (
        <div className="warning" role="status">
          This file is very long, so the AI reviewed only its first part. Static analysis covers
          the whole file.
        </div>
      )}
      <p className="muted">
        AI review ({review.model}): {review.confirmed} confirmed, {review.false_positives} false
        positives, {review.added} new
        {review.chunks > 1 && ` · reviewed in ${review.chunks} parts`}
      </p>
    </>
  )
}

function ToolErrors({ errors }) {
  const entries = Object.entries(errors ?? {})
  if (entries.length === 0) return null

  return (
    <div className="warning" role="status">
      <strong>Some analyzers failed, so results may be incomplete:</strong>
      <ul>
        {entries.map(([tool, reason]) => (
          <li key={tool}>
            {tool}: {reason}
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function App() {
  const [languages, setLanguages] = useState(FALLBACK_LANGUAGES)
  const [language, setLanguage] = useState(DEFAULT_LANGUAGE)
  const [code, setCode] = useState(SAMPLES[DEFAULT_LANGUAGE])
  const [result, setResult] = useState(null)
  const [analyzedCode, setAnalyzedCode] = useState(null) // the code `result` belongs to
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const [reveal, setReveal] = useState(null) // { line, endLine, seq } for the editor to jump to
  const [diffIssue, setDiffIssue] = useState(null) // issue whose fix is shown as a diff, or null

  // Line numbers in `result` only match the code that was analyzed. After an edit they may point
  // at the wrong lines, so say so instead of silently showing misplaced markers.
  const stale = result !== null && code !== analyzedCode

  function selectIssue(issue) {
    setDiffIssue(null) // "show me this line" means the code, not an open diff
    setReveal((previous) => ({ line: issue.line, endLine: issue.end_line ?? issue.line, seq: (previous?.seq ?? 0) + 1 }))
  }

  function applyShownFix(patchedCode) {
    // Every other fix's line numbers refer to the code before this change, so the results now
    // count as out of date (stale) and their fixes stay disabled until the next analysis.
    setCode(patchedCode)
    setDiffIssue(null)
  }

  useEffect(() => {
    getLanguages()
      .then(setLanguages)
      .catch(() => {}) // keep the fallback list; the health badge already reports the outage
  }, [])

  function handleLanguageChange(event) {
    const next = event.target.value
    // Swap in the new starter snippet only if the user hasn't edited the current one.
    if (code === SAMPLES[language] || !code.trim()) {
      setCode(SAMPLES[next] ?? '')
    }
    setLanguage(next)
    setResult(null)
    setError(null)
    setDiffIssue(null)
  }

  async function handleAnalyze() {
    setLoading(true)
    setError(null)
    setDiffIssue(null)
    try {
      const submitted = code
      setResult(await analyzeCode(submitted, language))
      setAnalyzedCode(submitted)
    } catch (err) {
      setResult(null)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const languageLabel = languages.find((item) => item.id === language)?.label ?? language

  return (
    <main className="app">
      <header className="header">
        <h1>AI Code Review</h1>
        <HealthBadge />
      </header>

      <div className="workspace">
        <section className="editor">
          <div className="toolbar">
            <label className="language-picker">
              Language
              <select value={language} onChange={handleLanguageChange}>
                {languages.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <button onClick={handleAnalyze} disabled={loading || !code.trim()}>
              {loading ? 'Analyzing… (the AI review can take up to a minute)' : 'Analyze'}
            </button>
          </div>
          <div className="editor-box">
            <Suspense fallback={<div className="editor-loading">Loading editor…</div>}>
              {/* The editor stays mounted (just hidden) while a diff is open, so its undo history
                  and scroll position survive. */}
              <div className="editor-layer" hidden={diffIssue !== null}>
                <CodeEditor
                  value={code}
                  onChange={setCode}
                  language={language}
                  label={`${languageLabel} code`}
                  issues={result?.issues ?? NO_ISSUES}
                  reveal={reveal}
                />
              </div>
            </Suspense>
            {/* A separate Suspense boundary on purpose: if the lazy diff chunk loaded inside the
                editor's boundary, React would suspend that boundary too, and the cleanup it runs
                disposes the Monaco editor ("InstantiationService has been disposed"). */}
            {diffIssue && (
              <Suspense fallback={<div className="editor-loading">Loading diff…</div>}>
                <FixDiff
                  code={code}
                  issue={diffIssue}
                  language={language}
                  canApply={!stale}
                  onApply={applyShownFix}
                  onClose={() => setDiffIssue(null)}
                />
              </Suspense>
            )}
          </div>
        </section>

        <section className="results">
          {error && <p className="error">{error}</p>}
          {!result && !error && (
            <p className="muted placeholder">
              Pick a language, paste or edit code, and press Analyze. Issues will appear here.
            </p>
          )}
          {result && (
            <>
              <h2>
                Score: <span className="score">{result.score}</span>/100
                <span className="result-language">{languageLabel}</span>
              </h2>
              {stale && (
                <div className="warning stale" role="status">
                  <span>Code changed since this analysis, so line numbers may be off.</span>
                  <button onClick={handleAnalyze} disabled={loading}>Re-analyze</button>
                </div>
              )}
              <ToolErrors errors={result.tool_errors} />
              <AIStatus review={result.ai_review} />
              <IssueList issues={result.issues} onSelect={selectIssue} onShowFix={setDiffIssue} stale={stale} />
            </>
          )}
        </section>
      </div>
    </main>
  )
}
