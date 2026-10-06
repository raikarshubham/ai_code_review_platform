// Our language ids (from the backend's /languages) -> Monaco language ids.
// Kept apart from monaco.js so it can be unit-tested without loading the editor.
export const MONACO_LANGUAGE = {
  python: 'python',
  javascript: 'javascript',
  typescript: 'typescript',
  java: 'java',
  csharp: 'csharp',
  go: 'go',
  rust: 'rust',
  cpp: 'cpp',
  c: 'c',
  php: 'php',
  ruby: 'ruby',
  swift: 'swift',
  kotlin: 'kotlin',
  objectivec: 'objective-c',
  sql: 'sql',
  html: 'html',
  css: 'css',
  yaml: 'yaml',
  // Monaco only has JSON as a full language service, which draws its own validation squiggles
  // that would compete with ours. JSON is JavaScript literal syntax, so that highlighter fits.
  json: 'javascript',
}

export function monacoLanguage(id) {
  return MONACO_LANGUAGE[id] ?? 'plaintext'
}
