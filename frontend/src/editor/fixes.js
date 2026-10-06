// Apply an AI fix: replace lines fix_start_line..fix_end_line (1-based, inclusive) with fixed_code.
// Pure, so it's unit-tested without a browser.

export function canApply(note) {
  return Boolean(note?.fixed_code && note.fix_start_line && note.fix_end_line)
}

function lineCount(lines, code) {
  // "a\nb\n".split("\n") is ['a', 'b', '']: a trailing newline doesn't start another line
  // (same rule as Python's splitlines on the backend, which produced the line numbers).
  return code.endsWith('\n') ? lines.length - 1 : lines.length
}

export function applyFix(code, note) {
  const { fixed_code: fixed, fix_start_line: start, fix_end_line: end } = note
  const eol = code.includes('\r\n') ? '\r\n' : '\n' // keep the file's own line endings
  const lines = code.split(/\r?\n/)
  // The backend already validated this range; checking again costs nothing and means a bad
  // fix can never silently overwrite the wrong lines.
  if (!Number.isInteger(start) || !Number.isInteger(end) || start < 1 || end < start || end > lineCount(lines, code)) {
    throw new RangeError(`fix range ${start}-${end} is outside the file`)
  }
  const replacement = fixed.replace(/\r?\n$/, '').split(/\r?\n/) // one trailing newline is not an extra line
  lines.splice(start - 1, end - start + 1, ...replacement)
  return lines.join(eol)
}
