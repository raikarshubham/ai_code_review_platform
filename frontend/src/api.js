// All backend calls live here so components don't hardcode URLs.
// VITE_API_URL is set per environment (e.g. the Render URL on Vercel); local dev uses the default.
const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export async function checkHealth() {
  const response = await fetch(`${API_URL}/health`)
  if (!response.ok) throw new Error(`Health check failed (${response.status})`)
  return response.json()
}

export async function analyzeCode(code) {
  const response = await fetch(`${API_URL}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
  })
  if (!response.ok) {
    // FastAPI validation errors come back as 422 with a `detail` array.
    const body = await response.json().catch(() => null)
    const detail = Array.isArray(body?.detail) ? body.detail[0]?.msg : body?.detail
    throw new Error(detail || `Analysis failed (${response.status})`)
  }
  return response.json()
}
