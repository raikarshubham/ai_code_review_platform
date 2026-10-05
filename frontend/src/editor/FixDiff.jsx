// Side-by-side "before / after" view of one AI fix, using Monaco's diff editor.
import { DiffEditor } from '@monaco-editor/react'
import { useEffect, useMemo, useRef, useState } from 'react'
import './monaco.js'
import { applyFix } from './fixes.js'
import { monacoLanguage } from './languages.js'
import { usePrefersDark } from './theme.js'

const OPTIONS = {
  readOnly: true,
  originalEditable: false,
  renderSideBySide: true,
  // Monaco falls back to a one-column (inline) diff below 900 px by default, and our editor column
  // is ~800 px wide. Two ~400 px panes still read fine for code; only really narrow screens
  // (phones, stacked layout) get the inline view.
  renderSideBySideInlineBreakpoint: 560,
  minimap: { enabled: false },
  scrollBeyondLastLine: false,
  automaticLayout: true,
  // Show only the changed lines plus a little context, not the whole file.
  hideUnchangedRegions: { enabled: true, contextLineCount: 3, minimumLineCount: 3 },
}

export default function FixDiff({ code, issue, language, canApply, onApply, onClose }) {
  const dark = usePrefersDark()
  const [copied, setCopied] = useState(false)
  const diffRef = useRef(null)

  // @monaco-editor/react disposes the two text models before detaching them from the diff
  // widget, which logs "TextModel got disposed before DiffEditorWidget model got reset". So the
  // library keeps the models (keepCurrent*Model below) and we release them here, in the right
  // order: detach first, then dispose.
  useEffect(() => () => {
    const diff = diffRef.current
    const models = diff?.getModel()
    try {
      diff?.setModel(null)
    } catch {
      // the widget may already be disposed; the models below still need releasing
    }
    models?.original.dispose()
    models?.modified.dispose()
  }, [])
  const { modified, error } = useMemo(() => {
    try {
      return { modified: applyFix(code, issue.ai), error: null }
    } catch (err) {
      return { modified: code, error: err.message }
    }
  }, [code, issue])

  async function copy() {
    await navigator.clipboard.writeText(issue.ai.fixed_code)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="fix-diff">
      <div className="fix-diff-bar">
        <span className="fix-diff-title">
          Fix for line {issue.line}: {issue.message}
          <span className="muted"> · lines {issue.ai.fix_start_line}–{issue.ai.fix_end_line}, before → after</span>
        </span>
        <span className="fix-diff-actions">
          <button
            className="primary"
            onClick={() => onApply(modified)}
            disabled={!canApply || Boolean(error)}
            title={canApply ? 'Replace these lines in the editor' : 'Re-analyze first: the code changed since this fix was suggested'}
          >
            Apply fix
          </button>
          <button onClick={copy}>{copied ? 'Copied' : 'Copy fix'}</button>
          <button onClick={onClose}>Close</button>
        </span>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="fix-diff-editor">
        <DiffEditor
          height="100%"
          language={monacoLanguage(language)}
          original={code}
          modified={modified}
          theme={dark ? 'vs-dark' : 'vs'}
          options={OPTIONS}
          keepCurrentOriginalModel
          keepCurrentModifiedModel
          onMount={(editor) => { diffRef.current = editor }}
          loading={<div className="editor-loading">Loading diff…</div>}
        />
      </div>
    </div>
  )
}
