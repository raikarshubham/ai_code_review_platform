// All backend calls live here so components don't hardcode URLs.
// VITE_API_URL is set per environment (e.g. the Render URL on Vercel); local dev uses the default.
import { getClientId } from './clientId.js'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export async function checkHealth() {
  const response = await fetch(`${API_URL}/health`)
  if (!response.ok) throw new Error(`Health check failed (${response.status})`)
  return response.json()
}

export async function getLanguages() {
  const response = await fetch(`${API_URL}/languages`)
  if (!response.ok) throw new Error(`Could not load languages (${response.status})`)
  return response.json()
}

// Just above the backend's 120 s LLM deadline, so the backend normally answers first (with
// static results and an ai_review.error) and this only fires if the server is truly stuck.
const ANALYZE_TIMEOUT_MS = 150_000

export async function analyzeCode(code, language) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), ANALYZE_TIMEOUT_MS)
  let response
  try {
    response = await fetch(`${API_URL}/analyze`, {
      method: 'POST',
      // The client id lets the backend save this analysis to this browser's history.
      headers: { 'Content-Type': 'application/json', 'X-Client-Id': getClientId() },
      body: JSON.stringify({ code, language }),
      signal: controller.signal,
    })
  } catch (err) {
    if (err.name === 'AbortError') throw new Error('Analysis timed out after 150 s. Please try again.')
    throw err
  } finally {
    clearTimeout(timer)
  }
  if (!response.ok) {
    // FastAPI validation errors come back as 422 with a `detail` array.
    const body = await response.json().catch(() => null)
    const detail = Array.isArray(body?.detail) ? body.detail[0]?.msg : body?.detail
    throw new Error(detail || `Analysis failed (${response.status})`)
  }
  return response.json()
}

// --- History (this browser's past analyses) ---------------------------------------------------
// 503 means the backend runs without a database; callers can hide the history UI then.

async function historyRequest(path, options = {}) {
  const response = await fetch(`${API_URL}/history${path}`, {
    ...options,
    headers: { 'X-Client-Id': getClientId() },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const error = new Error(body?.detail || `History request failed (${response.status})`)
    error.status = response.status
    throw error
  }
  return response.status === 204 ? null : response.json()
}

export const getHistory = (limit = 20) => historyRequest(`?limit=${limit}`)
export const getHistoryItem = (id) => historyRequest(`/${id}`)
export const deleteHistoryItem = (id) => historyRequest(`/${id}`, { method: 'DELETE' })
