// The code editor. Loaded lazily by App (React.lazy), so Monaco's ~MBs arrive in their own chunk
// after the page shell is already on screen.
import Editor from '@monaco-editor/react'
import { useEffect, useState } from 'react'
import './monaco.js'
import { monacoLanguage } from './languages.js'

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

export default function CodeEditor({ value, onChange, language, label }) {
  const dark = usePrefersDark()

  function handleMount(editor) {
    // Dev builds only (Vite strips this from production): lets the browser test scripts read
    // and set the code, since Monaco has no plain <textarea> to fill.
    if (import.meta.env.DEV) window.__codeEditor = editor
  }

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
