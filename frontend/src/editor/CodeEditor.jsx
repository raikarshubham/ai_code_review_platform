// The code editor. Loaded lazily by App (React.lazy), so Monaco's ~MBs arrive in their own chunk
// after the page shell is already on screen.
import Editor from '@monaco-editor/react'
import { useEffect, useRef, useState } from 'react'
import './monaco.js'
import { monacoLanguage } from './languages.js'
import { gutterDots, toMarkers } from './markers.js'

const MARKER_OWNER = 'review' // our markers, kept apart from any other source's

const DARK_QUERY = '(prefers-color-scheme: dark)'

function usePrefersDark() {
  const [dark, setDark] = useState(() => window.matchMedia(DARK_QUERY).matches)
  useEffect(() => {
    const query = window.matchMedia(DARK_QUERY)
    const update = () => setDark(query.matches)
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])
  return dark
}

const OPTIONS = {
  minimap: { enabled: false },
  glyphMargin: true, // room for the per-line severity dots
  fontSize: 14,
  tabSize: 4,
  scrollBeyondLastLine: false,
  automaticLayout: true, // re-measure when the panel is resized
}

/**
 * @param issues  issues to show as squiggles and gutter dots ([] for none)
 * @param reveal  { line, endLine, seq } from clicking an issue; seq makes a repeat click count
 */
export default function CodeEditor({ value, onChange, language, label, issues = [], reveal }) {
  const dark = usePrefersDark()
  const editorRef = useRef(null)
  const monacoRef = useRef(null)
  const dotsRef = useRef(null)
  const [ready, setReady] = useState(false)

  function handleMount(editor, monaco) {
    editorRef.current = editor
    monacoRef.current = monaco
    dotsRef.current = editor.createDecorationsCollection()
    setReady(true)
    // Dev builds only (Vite strips this from production): lets the browser test scripts read
    // and set the code, since Monaco has no plain <textarea> to fill.
    if (import.meta.env.DEV) window.__codeEditor = editor
  }

  // Squiggles + hover text, and one colored dot per line in the gutter.
  useEffect(() => {
    const editor = editorRef.current
    const monaco = monacoRef.current
    const model = editor?.getModel()
    if (!ready || !model) return
    const lines = {
      lineCount: model.getLineCount(),
      firstColumn: (line) => model.getLineFirstNonWhitespaceColumn(line) || 1,
      lastColumn: (line) => model.getLineMaxColumn(line),
    }
    monaco.editor.setModelMarkers(model, MARKER_OWNER, toMarkers(issues, monaco.MarkerSeverity, lines))
    dotsRef.current.set(
      gutterDots(issues, lines.lineCount).map(({ line, severity }) => ({
        range: new monaco.Range(line, 1, line, 1),
        options: { glyphMarginClassName: `gutter-dot gutter-dot-${severity}`, glyphMarginHoverMessage: { value: severity } },
      })),
    )
    // value is a dependency on purpose: an edit can change the line count, so markers are
    // re-clamped to lines that still exist.
  }, [ready, issues, value, language])

  // Clicking an issue in the list scrolls the editor to it and selects its lines.
  useEffect(() => {
    const editor = editorRef.current
    const model = editor?.getModel()
    if (!ready || !reveal || !model || reveal.line > model.getLineCount()) return
    const endLine = Math.min(reveal.endLine ?? reveal.line, model.getLineCount())
    editor.revealLinesInCenter(reveal.line, endLine)
    editor.setSelection({ startLineNumber: reveal.line, startColumn: 1, endLineNumber: endLine,
      endColumn: model.getLineMaxColumn(endLine) })
    editor.focus()
  }, [ready, reveal])

  return (
    <Editor
      height="100%"
      language={monacoLanguage(language)}
      value={value}
      onChange={(next) => onChange(next ?? '')}
      onMount={handleMount}
      theme={dark ? 'vs-dark' : 'vs'}
      options={{ ...OPTIONS, ariaLabel: label }}
      loading={<div className="editor-loading">Loading editor…</div>}
    />
  )
}
