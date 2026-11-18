import { useEffect, useRef, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import { api, streamChat } from './api'
import type { LocalDocument, Metrics, ModelMetadata, Reasoning, Result, Settings, Source } from './api'
import './style.css'

const navigation = [
  { id: 'chat', icon: '✦', title: 'Právny asistent' },
  { id: 'library', icon: '§', title: 'Právna databáza' },
  { id: 'documents', icon: '▤', title: 'Moje dokumenty' },
  { id: 'settings', icon: '⚙', title: 'Nastavenia' },
] as const

type Tab = typeof navigation[number]['id']
type Turn = { question: string; result: Result; simulated: boolean }
type Preferences = {
  model: string
  context: number
  temperature: number
  maxTokens: number
  reasoning: Reasoning
  measureMemory: boolean
  device: "auto" | "cpu"
}
const defaults: Preferences = {
  model: '', context: 4096, temperature: 0.15, maxTokens: 768,
  reasoning: 'auto', measureMemory: false, device: 'auto',
}
const reasoningLabels = { auto: 'Auto · podľa modelu', on: 'Zapnuté', off: 'Vypnuté' }

function stored<T>(key: string, fallback: T): T {
  try {
    const value = localStorage.getItem(key)
    return value ? JSON.parse(value) : fallback
  } catch {
    return fallback
  }
}

function persist(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // The running session remains usable when browser storage is disabled or full.
  }
}

function humanError(error: unknown) {
  return error instanceof Error ? error.message : 'Operácia zlyhala.'
}

function SourceCard({ source, number }: { source: Source; number?: number }) {
  const interval = source.effective_from
    ? `${source.effective_from} → ${source.effective_until
      ? `${source.effective_until} (bez tohto dňa)`
      : source.open_ended ? 'otvorený interval' : 'neznámy koniec'}`
    : 'Účinnosť neznáma'
  return <article className="source">
    {source.fictional && <span className="chip warning">Fiktívny zdroj</span>}
    {source.norm_status === 'repealed' && <span className="chip warning">Zrušené ustanovenie</span>}
    {source.norm_status === 'transitional' && <span className="chip warning">Prechodné ustanovenie</span>}
    <h3>{number !== undefined && `[${number}] `}{source.title}</h3>
    <p className="muted">{[
      source.law_number && `${source.law_number}/${source.law_year}`,
      source.section && (source.section.startsWith('cl-') ? `Čl. ${source.section.slice(3)}` : `§ ${source.section}`), source.paragraph && `ods. ${source.paragraph}`,
      source.letter && `písm. ${source.letter}`, source.case_number, source.decision_date,
    ].filter(Boolean).join(' · ')}</p>
    <p className="excerpt">{source.text}</p>
    <small>{source.authority} · {interval}</small>
    {!source.fictional && <small>{source.original_archived
      ? 'Originál uložený lokálne' : 'Pôvodný dokument treba overiť'}</small>}
    <small><code>{source.citation_id}</code></small>
    {source.source_url && <a href={source.source_url} target="_blank" rel="noopener noreferrer">Otvoriť pôvodný zdroj ↗</a>}
  </article>
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <label className="field"><span>{label}</span>{children}</label>
}

const formatNumber = new Intl.NumberFormat('sk', { maximumFractionDigits: 2 })

function measured(value: number | null, unit: string) {
  return value === null ? 'Nedostupné' : `${formatNumber.format(value)} ${unit}`
}

function Performance({ metrics, simulated }: { metrics: Metrics; simulated: boolean }) {
  const memory = metrics.memory
  return <details>
    <summary>{simulated ? 'Metriky simulácie' : 'Výkon odpovede'}</summary>
    <dl className="note">
      <dt>Celkový čas</dt><dd>{measured(metrics.seconds, 's')}</dd>
      {!simulated && <>
        <dt>Prvý token</dt><dd>{measured(metrics.first_token_seconds, 's')}</dd>
        <dt>Prvý token odpovede</dt><dd>{measured(metrics.first_answer_token_seconds, 's')}</dd>
        <dt>Vygenerované tokeny vrátane uvažovania</dt><dd>{measured(metrics.generated_tokens, 'tokenov')}</dd>
        <dt>Rýchlosť generovania</dt><dd>{measured(metrics.tokens_per_second, 'tok/s')}</dd>
      </>}
      {memory?.processes.map((process) => <div key={process.pid}>
        <dt>{process.role === 'backend' ? 'TM-Law' : 'Ollama'} · PID {process.pid} · špička RSS</dt>
        <dd>{measured(process.peak_rss_bytes / 1048576, 'MiB')}</dd>
      </div>)}
      {memory && !simulated && <>
        <dt>Spoločná špička PSS</dt>
        <dd>{measured(memory.combined_peak_pss_bytes === null ? null : memory.combined_peak_pss_bytes / 1048576, 'MiB')}</dd>
        {!memory.ollama_listener_measured && <dd>Proces Ollama sa nepodarilo priradiť k serveru.</dd>}
      </>}
    </dl>
  </details>
}

function App() {
  const [tab, setTab] = useState<Tab>('chat')
  const [dark, setDark] = useState(() => stored('tm-law-theme', false))
  const [settings, setSettings] = useState<Settings>()
  const [bootError, setBootError] = useState('')
  const [models, setModels] = useState<string[]>([])
  const [metadata, setMetadata] = useState<Record<string, ModelMetadata>>({})
  const [modelIssue, setModelIssue] = useState('')
  const [prefs, setPrefs] = useState<Preferences>(() => ({ ...defaults, ...stored('tm-law-preferences', {}) }))
  const [history, setHistory] = useState<Turn[]>(() => stored('tm-law-history', []))
  const [documents, setDocuments] = useState<LocalDocument[]>([])
  const [doc, setDoc] = useState('')
  const [question, setQuestion] = useState('')
  const [chatDate, setChatDate] = useState('')
  const [chatQuery, setChatQuery] = useState('')
  const [pending, setPending] = useState('')
  const [draft, setDraft] = useState('')
  const [thinking, setThinking] = useState(false)
  const [pendingWarning, setPendingWarning] = useState('')
  const [chatError, setChatError] = useState('')
  const [query, setQuery] = useState('')
  const [searchDate, setSearchDate] = useState('')
  const [kind, setKind] = useState('')
  const [caseNumber, setCaseNumber] = useState('')
  const [hits, setHits] = useState<Source[] | null>(null)
  const [searchNote, setSearchNote] = useState('')
  const [searchError, setSearchError] = useState('')
  const [docNote, setDocNote] = useState('')
  const [importNote, setImportNote] = useState('')
  const [uploading, setUploading] = useState(false)
  const [importing, setImporting] = useState(false)
  const controller = useRef<AbortController | null>(null)
  const latest = history.at(-1)
  const selectedModel = prefs.model || settings?.default_model || ''
  const modelInfo = metadata[selectedModel] ?? metadata[`${selectedModel}:latest`]
  const mode = settings?.simulated ? 'Testovací režim' : 'Lokálny režim'

  async function refreshModels() {
    setModelIssue('')
    try {
      const result = await api<{ models: string[]; metadata?: Record<string, ModelMetadata> }>('/models')
      setModels(result.models)
      setMetadata(result.metadata ?? {})
      if (!result.models.length) setModelIssue('V Ollame nie je nainštalovaný žiadny model.')
    } catch (error) {
      setModels([])
      setMetadata({})
      setModelIssue(humanError(error))
    }
  }

  async function refreshDocuments() {
    const result = await api<{ documents: LocalDocument[] }>('/documents')
    setDocuments(result.documents)
  }

  useEffect(() => {
    api<Settings>('/settings').then(setSettings).catch(() => setBootError('Lokálny backend nie je dostupný.'))
    void refreshModels()
    refreshDocuments().catch((error) => setDocNote(humanError(error)))
    return () => controller.current?.abort()
  }, [])

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? 'dark' : 'light'
    persist('tm-law-theme', dark)
  }, [dark])

  useEffect(() => persist('tm-law-history', history), [history])
  useEffect(() => persist('tm-law-preferences', prefs), [prefs])

  async function submitChat(event: FormEvent) {
    event.preventDefault()
    if (controller.current || question.trim().length < 3) return
    const current = new AbortController()
    controller.current = current
    setPending(question)
    setDraft('')
    setChatError('')
    setThinking(false)
    setPendingWarning('')
    let simulated = Boolean(settings?.simulated)
    try {
      await streamChat({
        question, query: chatQuery.trim() || null, as_of: chatDate || null, document_id: doc || null,
        options: {
          model: prefs.model || null, context_window: prefs.context,
          temperature: prefs.temperature, max_tokens: prefs.maxTokens,
          reasoning: settings?.simulated ? 'auto' : prefs.reasoning, measure_memory: prefs.measureMemory,
          device: prefs.device,
        },
      }, current.signal, (item) => {
        if (item.type === 'start') {
          simulated = item.simulated
          if (item.evidence_status === 'insufficient') setPendingWarning('Chýba právny podklad.')
          if (item.evidence_status === 'version_conflict') setPendingWarning('Nájdené znenia sa líšia.')
        }
        if (item.type === 'thinking') setThinking(true)
        if (item.type === 'delta') setDraft((previous) => previous + item.text)
        if (item.type === 'done') {
          setHistory((previous) => [...previous, { question, simulated, result: item }].slice(-30))
          setQuestion('')
        }
      })
    } catch (error) {
      setChatError(current.signal.aborted ? 'Generovanie bolo zastavené.' : humanError(error))
    } finally {
      controller.current = null
      setPending('')
      setDraft('')
    }
  }

  async function search(event: FormEvent) {
    event.preventDefault()
    const params = new URLSearchParams({ q: query })
    if (searchDate) params.set('as_of', searchDate)
    if (kind) params.set('kind', kind)
    if (kind === 'rozhodnutie' && caseNumber.trim()) params.set('case_number', caseNumber.trim())
    setSearchError('')
    setSearchNote('')
    setHits(null)
    try {
      const result = await api<{ hits: Source[]; note: string | null }>(`/search?${params}`)
      setHits(result.hits)
      setSearchNote(result.note ?? '')
    } catch (error) {
      setSearchError(humanError(error))
    }
  }

  async function legalImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const file = new FormData(form).get('legal')
    if (!(file instanceof File) || !file.size) return
    if (file.size > 5 * 1024 * 1024) {
      setImportNote('Súbor prekračuje limit 5 MiB.')
      return
    }
    setImporting(true)
    setImportNote('')
    try {
      const result = await api<{ version_id: string; created: boolean }>('/legal/import', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: await file.text(),
      })
      setImportNote(result.created ? `Importované znenie ${result.version_id}.` : 'Toto znenie už je v databáze.')
      form.reset()
    } catch (error) {
      setImportNote(humanError(error))
    } finally {
      setImporting(false)
    }
  }

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    setUploading(true)
    setDocNote('')
    try {
      const result = await api<LocalDocument>('/documents', { method: 'POST', body: new FormData(form) })
      await refreshDocuments()
      setDocNote(`Uložený dokument ${result.name}.`)
      form.reset()
    } catch (error) {
      setDocNote(humanError(error))
    } finally {
      setUploading(false)
    }
  }

  async function removeDocument(id: string) {
    try {
      await api(`/documents/${id}`, { method: 'DELETE' })
      if (doc === id) setDoc('')
      await refreshDocuments()
      setDocNote('Dokument bol odstránený zo zoznamu.')
    } catch (error) {
      setDocNote(humanError(error))
    }
  }

  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><span className="seal" aria-hidden="true">§</span><div>TM-Law<small>Thomas More Legal AI</small></div></div>
      <nav aria-label="Pracovný priestor">
        {navigation.map((item) => <button key={item.id} type="button"
          aria-current={tab === item.id ? 'page' : undefined}
          onClick={() => setTab(item.id)}>
          <span aria-hidden="true">{item.icon}</span>{item.title}
        </button>)}
      </nav>
      <div className="side-footer">
        <div className="local-mode"><span className={settings ? 'status-dot' : 'status-dot off'} />{settings ? mode : 'Backend nedostupný'}</div>
        <button type="button" className="theme" onClick={() => setDark(!dark)}>{dark ? '☀ Svetlý režim' : '◐ Tmavý režim'}</button>
      </div>
    </aside>
    <main>
      <header className="page-header"><h1>{navigation.find((item) => item.id === tab)?.title}</h1>
        <span className="chip">{settings ? `v${settings.version}` : 'Lokálna aplikácia'}</span></header>
      {bootError && <p className="alert" role="alert">{bootError}</p>}
      {tab === 'chat' && <div className="workspace">
        <section className="panel chat">
          <div className="panel-top"><span>{settings?.simulated ? 'Simulácia · bez inferencie' : prefs.model || settings?.default_model || 'Ollama'}</span>
            {history.length > 0 && <button className="text-button" type="button" disabled={Boolean(pending)} onClick={() => setHistory([])}>Vymazať históriu</button>}
          </div>
          {modelIssue && <p className="alert" role="status">{modelIssue}</p>}
          {!history.length && !pending && <div className="empty"><span className="empty-icon" aria-hidden="true">§</span>
            <h2>S čím vám môžem pomôcť?</h2><p>Položte právnu otázku alebo pripojte dokument. Rozhodujúci dátum použijeme pri výbere znenia.</p></div>}
          <div className="transcript">
            {history.map((turn, index) => <article className="turn" key={index}>
              <p className="question">{turn.question}</p>
              {turn.simulated && <span className="chip warning">Testovacia odpoveď</span>}
              <p className="answer">{turn.result.answer}</p>
              {turn.result.notes.map((note) => <p className="muted note" key={note}>{note}</p>)}
              {turn.result.retrieved_ids && <p className="muted note">
                Nájdené úseky: {turn.result.retrieved_ids.length} · Overené identifikátory: {turn.result.citations.length}
              </p>}
              {turn.result.metrics && <Performance metrics={turn.result.metrics} simulated={turn.simulated} />}
              {turn.result.rejected.length > 0 && <p className="alert">Neoverené odkazy: {turn.result.rejected.length}</p>}
              {index < history.length - 1 && turn.result.citations.length > 0 && <details>
                <summary>Zdroje odpovede</summary>
                {turn.result.citations.map((source, i) => <SourceCard source={source} number={i + 1} key={source.citation_id} />)}
              </details>}
            </article>)}
            {pending && <article className="turn">
              <p className="question">{pending}</p>
              <small className="muted" role="status">
                {thinking && !draft ? 'Model uvažuje…' : 'Generujem · citácie čakajú na kontrolu'}
              </small>
              {pendingWarning && <p className="alert">{pendingWarning}</p>}
              <p className="answer">{draft}</p>
            </article>}
          </div>
          {chatError && <p className="alert" role="alert">{chatError}</p>}
          <form className="composer" onSubmit={submitChat}>
            <Field label="Právna otázka"><textarea value={question} onChange={(event) => setQuestion(event.target.value)}
              rows={3} minLength={3} maxLength={4000} placeholder="Napíšte svoju otázku…" required /></Field>
            <div className="form-row">
              <Field label="Rozhodujúci dátum"><input type="date" value={chatDate} onChange={(event) => setChatDate(event.target.value)} /></Field>
              <Field label="Súkromný dokument"><select value={doc} onChange={(event) => setDoc(event.target.value)}>
                <option value="">Bez dokumentu</option>
                {documents.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select></Field>
              {pending
                ? <button key="stop" type="button" className="secondary" onClick={(event) => {
                  event.preventDefault()
                  controller.current?.abort()
                }}>Zastaviť</button>
                : <button key="send" type="submit" className="primary" disabled={question.trim().length < 3}>Odoslať ↑</button>}
            </div>
            <details><summary>Spresniť vyhľadávanie</summary>
              <Field label="Hľadané výrazy, číslo predpisu alebo paragraf">
                <input value={chatQuery} maxLength={400} onChange={(event) => setChatQuery(event.target.value)} />
              </Field>
            </details>
          </form>
        </section>
        <aside className="panel evidence" aria-label="Použité zdroje">
          <div className="panel-top"><h2>Použité zdroje</h2><span className="chip">{latest?.result.citations.length ?? 0}</span></div>
          {latest?.result.citations.length
            ? latest.result.citations.map((source, i) => <SourceCard key={source.citation_id} number={i + 1} source={source} />)
            : <p className="muted">Tu sa zobrazia odkazy z dokončenej odpovede, ktoré prešli kontrolou identifikátora.</p>}
        </aside>
      </div>}
      {tab === 'library' && <section className="panel stack">
        <form className="stack" onSubmit={search}>
          <Field label="Hľadaný výraz"><input placeholder="Napríklad evidencia, 9999/2099 alebo § 7" maxLength={400}
            value={query} onChange={(event) => setQuery(event.target.value)} /></Field>
          <div className="form-row">
            <Field label="Typ zdroja"><select value={kind} onChange={(event) => setKind(event.target.value)}>
              <option value="">Všetky typy</option><option>predpis</option><option>rozhodnutie</option><option value="eu">Právo EÚ</option><option>iný</option>
            </select></Field>
            {kind === 'rozhodnutie' && <Field label="Spisová značka"><input value={caseNumber}
              maxLength={240} onChange={(event) => setCaseNumber(event.target.value)} /></Field>}
            <Field label="Rozhodujúci dátum"><input type="date" value={searchDate} onChange={(event) => setSearchDate(event.target.value)} /></Field>
            <button className="primary">Vyhľadať</button>
          </div>
        </form>
        {searchError && <p className="alert" role="alert">{searchError}</p>}
        {searchNote && <p className="muted">{searchNote}</p>}
        {hits?.length === 0 && <p className="muted">Žiadne výsledky</p>}
        {hits?.map((source) => <SourceCard key={source.citation_id} source={source} />)}
        <details><summary>Importovať znenie predpisu alebo rozhodnutie</summary>
          <form className="form-row" onSubmit={legalImport}>
            <Field label="Štruktúrovaný súbor JSON"><input name="legal" type="file" accept=".json,application/json" required /></Field>
            <button className="secondary" disabled={importing}>{importing ? 'Importujem…' : 'Importovať'}</button>
          </form>
          {importNote && <p role="status">{importNote}</p>}
        </details>
      </section>}
      {tab === 'documents' && <section className="panel stack">
        <p className="muted">TXT, PDF s textovou vrstvou alebo DOCX. Najviac 8 MiB na súbor. Extrahovaný text sa ukladá lokálne bez šifrovania.</p>
        <form className="form-row" onSubmit={upload}>
          <Field label="Súbor"><input type="file" name="file" accept=".txt,.pdf,.docx" required /></Field>
          <button className="primary" disabled={uploading}>{uploading ? 'Spracúvam…' : 'Pridať dokument'}</button>
        </form>
        {docNote && <p role="status">{docNote}</p>}
        {documents.length === 0 && <p className="muted">Zatiaľ nemáte žiadny dokument.</p>}
        {documents.map((item) => <div className="document-row" key={item.id}><strong>{item.name}</strong>
          <div className="form-row">
            <button type="button" className="secondary" onClick={() => { setDoc(item.id); setTab('chat') }}>Otvoriť v chate</button>
            <button type="button" className="text-button" onClick={() => void removeDocument(item.id)}>Odstrániť</button>
          </div></div>)}
      </section>}
      {tab === 'settings' && <section className="panel stack">
        <Field label="Lokálny model"><select value={prefs.model} onChange={(event) => setPrefs({ ...prefs, model: event.target.value })}>
          <option value="">Predvolený · {settings?.default_model ?? 'Ollama'}</option>
          {prefs.model && !models.includes(prefs.model) && <option>{prefs.model}</option>}
          {models.map((model) => <option key={model}>{model}</option>)}
        </select></Field>
        {modelInfo && <p className="muted note">{[
          modelInfo.experimental ? 'Experimentálny TM-Law' : null,
          modelInfo.family, modelInfo.parameter_size, modelInfo.quantization_level, modelInfo.format,
          modelInfo.disk_size_bytes === null ? null : measured(modelInfo.disk_size_bytes / 1073741824, 'GiB na disku'),
        ].filter(Boolean).join(' · ')}</p>}
        <Field label="Výpočtové zariadenie"><select value={prefs.device} disabled={settings?.simulated}
          onChange={(event) => setPrefs({ ...prefs, device: event.target.value as Preferences['device'] })}>
          <option value="auto">Auto · podľa Ollamy</option>
          <option value="cpu">Len CPU</option>
        </select></Field>
        <Field label="Uvažovanie"><select value={prefs.reasoning} disabled={settings?.simulated}
          onChange={(event) => setPrefs({ ...prefs, reasoning: event.target.value as Reasoning })}>
          {Object.entries(reasoningLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select></Field>
        <label className="checkbox"><input type="checkbox" checked={prefs.measureMemory}
          onChange={(event) => setPrefs({ ...prefs, measureMemory: event.target.checked })} />
          Merať pamäť procesov pri odpovedi
        </label>
        <div className="form-row">
          <Field label="Kontext"><select value={prefs.context} onChange={(event) => {
            const context = Number(event.target.value)
            setPrefs({ ...prefs, context, maxTokens: Math.min(prefs.maxTokens, context / 2) })
          }}>
            {[2048, 4096, 8192, 16384, 32768].map((n) => <option key={n}>{n}</option>)}
          </select></Field>
          <Field label="Teplota"><input type="number" min="0" max="1" step=".05" value={prefs.temperature}
            onChange={(event) => setPrefs({ ...prefs, temperature: Math.min(1, Math.max(0, Number(event.target.value))) })} /></Field>
          <Field label="Limit generovania"><select value={prefs.maxTokens} onChange={(event) => setPrefs({ ...prefs, maxTokens: Number(event.target.value) })}>
            {[256, 512, 768, 1024, 2048, 4096, 8192].filter((n) => n <= prefs.context / 2).map((n) => <option key={n}>{n}</option>)}
          </select></Field>
          <button type="button" className="secondary" onClick={() => void refreshModels()}>Obnoviť zoznam modelov</button>
        </div>
        {modelIssue && <p className="alert" role="status">{modelIssue}</p>}
        <dl>
          <dt>Adresa runtime · TM_LAW_OLLAMA_URL</dt><dd>{settings?.runtime_url ?? 'Testovací adaptér alebo nedostupný server'}</dd>
          <dt>Úložisko · TM_LAW_DATA_DIR</dt><dd>{settings?.data_directory ?? 'Nedostupné'}</dd>
          <dt>Jazyk</dt><dd>Slovenčina</dd>
        </dl>
      </section>}
      <footer>TM-Law · Lokálny právny výskum a práca s dokumentmi</footer>
    </main>
  </div>
}

createRoot(document.getElementById('root')!).render(<App />)
