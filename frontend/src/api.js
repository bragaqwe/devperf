const BASE = '/api/v1'
async function request(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } }
  if (body !== undefined) opts.body = JSON.stringify(body)
  const res = await fetch(`${BASE}${path}`, opts)
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status}: ${text}`)
  }
  if (res.status === 204) return null
  return res.json()
}
export const api = {
  get:    p     => request('GET',    p),
  post:   (p,b) => request('POST',   p, b),
  put:    (p,b) => request('PUT',    p, b),
  delete: p     => request('DELETE', p),
}
