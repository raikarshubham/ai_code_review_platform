// This browser's past analyses: open one again, delete it, or clear them all.
const SEVERITIES = ['critical', 'high', 'medium', 'low', 'info']

function formatTime(iso) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

/**
 * @param available  false when IndexedDB is missing or blocked in this browser
 * @param items      newest first, list fields only (see store.js)
 * @param labels     language id -> display name
 */
export default function HistoryList({ available, items, labels, onOpen, onDelete, onClear }) {
  if (!available) {
    return (
      <p className="muted placeholder">
        History isn't available in this browser (storage is blocked or turned off). Analysis still works.
      </p>
    )
  }
  if (items.length === 0) {
    return (
      <p className="muted placeholder">
        No analyses yet. Each one you run is saved here, in this browser only.
      </p>
    )
  }

  return (
    <>
      <div className="history-bar">
        <span className="muted">
          {items.length} saved in this browser only, never on the server.
        </span>
        <button className="link-button" onClick={onClear}>Clear history</button>
      </div>
      <ul className="history">
        {items.map((item) => (
          <li key={item.id} className="history-item">
            <span className="history-score" title="Score">{item.score}</span>
            <span className="history-main">
              <span>
                {labels[item.language] ?? item.language} · {item.lines} {item.lines === 1 ? 'line' : 'lines'}
              </span>
              <span className="meta">{formatTime(item.createdAt)}</span>
            </span>
            <span className="history-counts">
              {SEVERITIES.filter((severity) => item.summary?.[severity] > 0).map((severity) => (
                <span key={severity} className={`severity severity-${severity}`} title={severity}>
                  {item.summary[severity]}
                </span>
              ))}
              {item.issueCount === 0 && <span className="muted">no issues</span>}
            </span>
            <span className="history-actions">
              <button className="show-fix" onClick={() => onOpen(item.id)}>Open</button>
              <button className="link-button" onClick={() => onDelete(item.id)} aria-label={`Delete analysis from ${formatTime(item.createdAt)}`}>
                Delete
              </button>
            </span>
          </li>
        ))}
      </ul>
    </>
  )
}
