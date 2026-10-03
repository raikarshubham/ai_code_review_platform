import { useEffect, useState } from 'react'
import { analyzeCode, checkHealth } from './api.js'
import './App.css'

const STARTER_CODE = `def process(data):
    try:
        result = int(data) * 2
    except ValueError:
        print("invalid input")
    return result
`

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

export default function App() {
  const [code, setCode] = useState(STARTER_CODE)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  async function handleAnalyze() {
    setLoading(true)
    setError(null)
    try {
      setResult(await analyzeCode(code))
    } catch (err) {
      setResult(null)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="app">
      <header className="header">
        <h1>AI Code Review</h1>
        <HealthBadge />
      </header>

      <section className="editor">
        <textarea
          value={code}
          onChange={(event) => setCode(event.target.value)}
          spellCheck={false}
          aria-label="Python code"
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
          </h2>
          <IssueList issues={result.issues} />
        </section>
      )}
    </main>
  )
}
