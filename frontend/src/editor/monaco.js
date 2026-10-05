// Monaco setup: bundled with the app (no CDN), editor core plus syntax highlighting only.
//
// @monaco-editor/react normally downloads Monaco from a CDN at runtime. loader.config({ monaco })
// points it at this bundled copy instead, so the app works offline and has no third-party
// runtime dependency.
//
// We import the editor core and the per-language highlighters ("basic languages"), NOT the full
// Monaco build: that one also runs the TypeScript/JSON/CSS/HTML language services, which draw
// their own error squiggles that would compete with our analysis results.
import { loader } from '@monaco-editor/react'
import * as monaco from 'monaco-editor/editor.js'
import EditorWorker from 'monaco-editor/editor/editor.worker.js?worker'
// Monaco's icon font (fold arrows, diff gutter, "N hidden lines"). The editor core above doesn't
// include it; without it every icon renders as an empty box.
import 'monaco-editor/features/codicon/register.js'

import 'monaco-editor/languages/definitions/python/register.js'
import 'monaco-editor/languages/definitions/javascript/register.js'
import 'monaco-editor/languages/definitions/typescript/register.js'
import 'monaco-editor/languages/definitions/java/register.js'
import 'monaco-editor/languages/definitions/csharp/register.js'
import 'monaco-editor/languages/definitions/go/register.js'
import 'monaco-editor/languages/definitions/rust/register.js'
import 'monaco-editor/languages/definitions/cpp/register.js' // registers both c and cpp
import 'monaco-editor/languages/definitions/php/register.js'
import 'monaco-editor/languages/definitions/ruby/register.js'
import 'monaco-editor/languages/definitions/swift/register.js'
import 'monaco-editor/languages/definitions/kotlin/register.js'
import 'monaco-editor/languages/definitions/objective-c/register.js'
import 'monaco-editor/languages/definitions/sql/register.js'
import 'monaco-editor/languages/definitions/html/register.js'
import 'monaco-editor/languages/definitions/css/register.js'
import 'monaco-editor/languages/definitions/yaml/register.js'

// Only the core editor worker (diffing, word ranges); no language-service workers.
self.MonacoEnvironment = { getWorker: () => new EditorWorker() }

loader.config({ monaco })

export { monaco }
