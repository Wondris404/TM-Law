export type Source = {
  citation_id: string
  title: string
  kind: string
  authority: string
  law_number: number | null
  law_year: number | null
  section: string | null
  paragraph: string | null
  letter: string | null
  effective_from: string | null
  effective_until: string | null
  open_ended: boolean
  case_number: string | null
  decision_date: string | null
  norm_status?: 'in_force' | 'repealed' | 'transitional' | 'unknown' | null
  original_sha256?: string | null
  original_archived?: boolean
  context_truncated?: boolean
  fictional: boolean
  version_id: string
  source_url: string | null
  text: string
}

export type Settings = {
  version: string
  simulated: boolean
  default_model: string
  runtime_url: string | null
  data_directory: string
  language: string
  peak_ram_bytes: number | null
}

export type LocalDocument = { id: string; name: string }

export type ModelMetadata = {
  tag: string
  family: string | null
  parameter_size: string | null
  quantization_level: string | null
  format: string | null
  disk_size_bytes: number | null
  experimental: boolean
}

export type Reasoning = 'auto' | 'on' | 'off'

export type Metrics = {
  seconds: number
  first_token_seconds: number | null
  first_answer_token_seconds: number | null
  generated_tokens: number | null
  tokens_per_second: number | null
  memory?: {
    samples: number
    ollama_listener_measured: boolean
    combined_peak_pss_bytes: number | null
    processes: { role: 'backend' | 'ollama' | 'ollama_worker'; pid: number; peak_rss_bytes: number }[]
  }
}

export type Result = {
  type: 'done'
  answer: string
  citations: Source[]
  rejected: string[]
  retrieved_ids?: string[]
  verified_ids?: string[]
  reasoning?: { requested: Reasoning; sent_to_ollama: boolean | string | null; thinking_observed: boolean }
  metrics?: Metrics
  notes: string[]
}

export type Event = Result
  | { type: 'start'; simulated: boolean; notes: string[]; evidence_status: string }
  | { type: 'thinking' }
  | { type: 'delta'; text: string }
  | { type: 'error'; message: string }

async function checked(response: Response) {
  if (response.ok) return response
  const body = await response.json().catch(() => null)
  const detail = body?.detail
  const validation = Array.isArray(detail)
    ? detail.map((issue) => `${issue.loc.slice(1).join('.')}: ${issue.msg}`).join(' · ')
    : null
  throw new Error(typeof detail === 'string' ? detail : validation || `Požiadavka zlyhala (${response.status}).`)
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await checked(await fetch(`/api${path}`, init))
  return response.json()
}

export async function streamChat(payload: object, signal: AbortSignal, consume: (event: Event) => void) {
  const response = await checked(await fetch('/api/chat', {
    method: 'POST', signal, headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }))
  if (!response.body) throw new Error('Server neposlal odpoveď.')
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  let finished = false
  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += value
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) {
        if (!line.trim()) continue
        const event: Event = JSON.parse(line)
        if (event.type === 'error') throw new Error(event.message)
        consume(event)
        finished ||= event.type === 'done'
      }
    }
    if (!finished) throw new Error('Spojenie sa ukončilo pred dokončením odpovede.')
  } finally {
    await reader.cancel().catch(() => undefined)
    reader.releaseLock()
  }
}
