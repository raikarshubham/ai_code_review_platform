import { useEffect, useState } from 'react'
import { analyzeCode, checkHealth, getLanguages } from './api.js'
import { SAMPLES } from './samples.js'
import './App.css'

const DEFAULT_LANGUAGE = 'python'

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

function IssueList({ issues }) {
  if (issues.length === 0) return <p className="muted">No issues found.</p>

  return (
    <ul className="issues">
      {issues.map((issue, index) => (
        <li key={`${issue.tool}-${issue.rule_id}-${issue.line}-${index}`} className="issue">
          <span className={`severity severity-${issue.severity}`}>{issue.severity}</span>
          <span className="line">Line {issue.line}</span>
          <span className="message">{issue.message}</span>
          <span className="meta">
            {issue.tool} · {issue.rule_id} · {issue.category}
          </span>
        </li>
      ))}
    </ul>
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
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

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
  }

  async function handleAnalyze() {
    setLoading(true)
    setError(null)
    try {
      setResult(await analyzeCode(code, language))
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

      <section className="editor">
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
        <textarea
          value={code}
          onChange={(event) => setCode(event.target.value)}
          spellCheck={false}
          aria-label={`${languageLabel} code`}
        />
        <button onClick={handleAnalyze} disabled={loading || !code.trim()}>
          {loading ? 'Analyzing…' : 'Analyze'}
        </button>
      </section>

      {error && <p className="error">{error}</p>}

      {result && (
        <section className="results">
          <h2>
            Score: <span className="score">{result.score}</span>/100
            <span className="result-language">{languageLabel}</span>
          </h2>
          <ToolErrors errors={result.tool_errors} />
          <IssueList issues={result.issues} />
        </section>
      )}
    </main>
  )
}
