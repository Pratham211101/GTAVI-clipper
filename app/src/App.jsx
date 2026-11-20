import React, { useEffect, useMemo, useState } from 'react'
import {
  Bot,
  CalendarClock,
  CheckCircle2,
  Clock,
  Cpu,
  ExternalLink,
  Film,
  Instagram,
  Loader2,
  Play,
  RefreshCw,
  Save,
  Search,
  Sparkles,
  Trash2,
  Upload,
  X,
  Youtube,
  Zap,
} from 'lucide-react'

const STREAMER_PRESETS = ['Kai Cenat', 'IShowSpeed', 'Typical Gamer', 'Tarik', 'xQc']
const INTERVAL_PRESETS = [
  { label: 'Immediate (0m)', value: 0 },
  { label: '15 mins', value: 15 },
  { label: '30 mins', value: 30 },
  { label: '1 hour', value: 60 },
  { label: '2 hours', value: 120 },
]

function formatCountdown(ts) {
  if (!ts) return ''
  const diffSec = Math.round(ts - Date.now() / 1000)
  if (diffSec <= 15) return 'Now'
  const mins = Math.round(diffSec / 60)
  if (mins < 60) return `in ${mins}m`
  const h = Math.floor(mins / 60)
  const m = mins % 60
  return m ? `in ${h}h ${m}m` : `in ${h}h`
}

async function apiFetch(url, options = {}) {
  const res = await fetch(url, options)
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new Error(data.detail || data.error || `Request failed (${res.status})`)
  }
  return data
}

function ClipCard({ clip, ytConnected, igConnected, schedInterval, onSaved, onUploaded, onScheduleOne }) {
  const [title, setTitle] = useState(clip.title || '')
  const [caption, setCaption] = useState(clip.caption || '')
  const [tagsText, setTagsText] = useState((clip.hashtags || []).join(' '))
  const [saving, setSaving] = useState(false)
  const [uploadingYt, setUploadingYt] = useState(false)
  const [uploadingIg, setUploadingIg] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [msg, setMsg] = useState(null)

  useEffect(() => {
    setTitle(clip.title || '')
    setCaption(clip.caption || '')
    setTagsText((clip.hashtags || []).join(' '))
  }, [clip.id, clip.title, clip.caption, clip.hashtags])

  const parsedTags = tagsText
    .split(/[\s,]+/)
    .map((t) => t.trim())
    .filter(Boolean)

  async function handleSave() {
    setSaving(true)
    setMsg(null)
    try {
      const data = await apiFetch('/api/clips', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: clip.id,
          title,
          caption,
          hashtags: parsedTags,
        }),
      })
      onSaved(data.clip)
      setMsg({ ok: true, text: 'Saved title & caption' })
    } catch (err) {
      setMsg({ ok: false, text: err.message })
    } finally {
      setSaving(false)
    }
  }

  async function uploadTo(platform) {
    if (platform === 'yt') setUploadingYt(true)
    if (platform === 'ig') setUploadingIg(true)
    setMsg(null)
    try {
      const endpoint = platform === 'yt' ? '/api/upload/youtube' : '/api/upload/instagram'
      const data = await apiFetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          clip_id: clip.id,
          title,
          caption,
          hashtags: parsedTags,
          privacy: 'public',
        }),
      })
      onUploaded(data.clip)
      setMsg({ ok: true, text: `Uploaded to ${platform === 'yt' ? 'YouTube Shorts' : 'Instagram Reels'}!` })
    } catch (err) {
      setMsg({ ok: false, text: err.message })
    } finally {
      if (platform === 'yt') setUploadingYt(false)
      if (platform === 'ig') setUploadingIg(false)
    }
  }

  async function uploadBoth() {
    await uploadTo('yt')
    await uploadTo('ig')
  }

  const ytUpload = clip.uploads?.youtube
  const igUpload = clip.uploads?.instagram

  return (
    <div className="clip-card">
      <div className="video-wrap">
        {playing ? (
          <video controls autoPlay src={clip.video_url} />
        ) : (
          <button
            type="button"
            className="video-poster-btn"
            onClick={() => setPlaying(true)}
            title="Click to play video"
          >
            {clip.check_url ? (
              <img src={clip.check_url} alt={clip.title} loading="lazy" />
            ) : (
              <Film size={40} color="#475569" />
            )}
            <span className="play-circle">
              <Play size={24} fill="white" />
            </span>
          </button>
        )}
        <span className="score-tag">Score {clip.score}</span>
        <span className="creator-tag">{clip.creator}</span>
      </div>

      <div className="clip-body">
        <div className="clip-meta-line">
          <span>{clip.seconds}s · {clip.look} · {clip.size_mb} MB</span>
          <span>{clip.date || 'Today'}</span>
        </div>

        <div className="field">
          <label>Catchy Video Title</label>
          <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>

        <div className="field">
          <label>Post Caption</label>
          <textarea className="textarea" rows={2} value={caption} onChange={(e) => setCaption(e.target.value)} />
        </div>

        <div className="field">
          <label>Hashtags</label>
          <input className="input" value={tagsText} onChange={(e) => setTagsText(e.target.value)} />
        </div>

        {(ytUpload || igUpload) && (
          <div className="uploaded-links">
            {ytUpload?.url && (
              <a className="link-badge" href={ytUpload.url} target="_blank" rel="noreferrer">
                <CheckCircle2 size={12} /> YouTube Short <ExternalLink size={11} />
              </a>
            )}
            {igUpload && (
              <a
                className="link-badge"
                href={igUpload.url || 'https://www.instagram.com/'}
                target="_blank"
                rel="noreferrer"
              >
                <CheckCircle2 size={12} /> Instagram Reel <ExternalLink size={11} />
              </a>
            )}
          </div>
        )}

        {msg && (
          <div className={`alert ${msg.ok ? 'alert-ok' : 'alert-err'}`} style={{ marginBottom: 0 }}>
            {msg.text}
          </div>
        )}

        <div className="clip-actions">
          <button className="btn btn-secondary btn-sm span-2" onClick={handleSave} disabled={saving}>
            {saving ? <Loader2 size={14} className="spin" /> : <Save size={14} />}
            Save Title & Caption
          </button>

          <button
            className="btn btn-yt btn-sm"
            disabled={!ytConnected || uploadingYt}
            title={ytConnected ? 'Upload directly to YouTube Shorts' : 'Connect YouTube account first'}
            onClick={() => uploadTo('yt')}
          >
            {uploadingYt ? <Loader2 size={14} className="spin" /> : <Youtube size={14} />}
            {ytUpload ? 'Re-upload YT' : 'Post YT Short'}
          </button>

          <button
            className="btn btn-ig btn-sm"
            disabled={!igConnected || uploadingIg}
            title={igConnected ? 'Upload directly to Instagram Reels' : 'Connect Instagram account first'}
            onClick={() => uploadTo('ig')}
          >
            {uploadingIg ? <Loader2 size={14} className="spin" /> : <Instagram size={14} />}
            {igUpload ? 'Re-upload IG' : 'Post IG Reel'}
          </button>

          {ytConnected && igConnected && (
            <button
              className="btn btn-both btn-sm span-2"
              disabled={uploadingYt || uploadingIg}
              onClick={uploadBoth}
            >
              <Upload size={14} /> Upload to Both YT & Instagram
            </button>
          )}

          {(ytConnected || igConnected) && (
            <button
              className="btn btn-secondary btn-sm span-2"
              onClick={() => onScheduleOne(clip)}
              title="Add this clip to the next drip schedule slot"
            >
              <Clock size={14} /> Schedule (+{schedInterval}m)
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default function App() {
  const [status, setStatus] = useState(null)
  const [clips, setClips] = useState([])
  const [jobs, setJobs] = useState([])
  const [schedule, setSchedule] = useState([])
  const [creatorFilter, setCreatorFilter] = useState('ALL')
  const [searchText, setSearchText] = useState('')

  // 1-Click Batch Uploader & Scheduler state
  const [schedPlatforms, setSchedPlatforms] = useState('both') // both | youtube | instagram
  const [schedInterval, setSchedInterval] = useState(15)
  const [schedStartDelay, setSchedStartDelay] = useState(0)
  const [schedYtNative, setSchedYtNative] = useState(true)
  const [schedSkipUploaded, setSchedSkipUploaded] = useState(true)
  const [schedBusy, setSchedBusy] = useState(false)
  const [schedMsg, setSchedMsg] = useState(null)

  // 1-Click Generator form
  const [query, setQuery] = useState('Kai Cenat')
  const [topic, setTopic] = useState('GTA 6')
  const [clipCount, setClipCount] = useState(3)
  const [section, setSection] = useState('0:20:00-1:00:00')
  const [when, setWhen] = useState('week')
  const [brain, setBrain] = useState('smart')
  const [focus, setFocus] = useState('')
  const [autoYt, setAutoYt] = useState(false)
  const [autoIg, setAutoIg] = useState(false)

  const [findingStreams, setFindingStreams] = useState(false)
  const [foundStreams, setFoundStreams] = useState([])
  const [submittingJob, setSubmittingJob] = useState(false)
  const [genError, setGenError] = useState(null)

  // Modals
  const [showYtModal, setShowYtModal] = useState(false)
  const [showIgModal, setShowIgModal] = useState(false)
  const [ytClientId, setYtClientId] = useState('')
  const [ytClientSecret, setYtClientSecret] = useState('')
  const [ytBusy, setYtBusy] = useState(false)
  const [ytErr, setYtErr] = useState(null)
  const [ytAuthUrl, setYtAuthUrl] = useState(null)

  const [igMode, setIgMode] = useState('session') // session | password
  const [igUser, setIgUser] = useState('')
  const [igPass, setIgPass] = useState('')
  const [ig2fa, setIg2fa] = useState('')
  const [igSessionId, setIgSessionId] = useState('')
  const [igBusy, setIgBusy] = useState(false)
  const [igErr, setIgErr] = useState(null)

  async function refreshAll() {
    try {
      const [st, cl, jb, sc] = await Promise.all([
        apiFetch('/api/status'),
        apiFetch('/api/clips'),
        apiFetch('/api/jobs'),
        apiFetch('/api/schedule'),
      ])
      setStatus(st)
      setClips(cl.clips || [])
      setJobs(jb.jobs || [])
      setSchedule(sc.schedule || [])
    } catch (err) {
      console.error(err)
    }
  }

  useEffect(() => {
    refreshAll()
  }, [])

  // Poll jobs & clips while any job is running or queued
  useEffect(() => {
    const active = jobs.some((j) => j.status === 'running' || j.status === 'queued')
    if (!active) return
    const timer = setInterval(async () => {
      try {
        const jb = await apiFetch('/api/jobs')
        setJobs(jb.jobs || [])
        if (!(jb.jobs || []).some((j) => j.status === 'running' || j.status === 'queued')) {
          const cl = await apiFetch('/api/clips')
          setClips(cl.clips || [])
        }
      } catch {
        // ignore transient poll error
      }
    }, 2500)
    return () => clearInterval(timer)
  }, [jobs])

  // Poll schedule & clips while any scheduled item is pending or uploading
  useEffect(() => {
    const pending = schedule.some((s) => s.status === 'scheduled' || s.status === 'uploading')
    if (!pending) return
    const timer = setInterval(async () => {
      try {
        const [sc, cl] = await Promise.all([
          apiFetch('/api/schedule'),
          apiFetch('/api/clips'),
        ])
        setSchedule(sc.schedule || [])
        setClips(cl.clips || [])
      } catch {
        // ignore transient poll error
      }
    }, 5000)
    return () => clearInterval(timer)
  }, [schedule])

  async function handleFindStreams() {
    setFindingStreams(true)
    setGenError(null)
    try {
      const data = await apiFetch('/api/find', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, topic, when, count: 5 }),
      })
      setFoundStreams(data.streams || [])
      if (!(data.streams || []).length) {
        setGenError('No streams found for that query. Try pasting the YouTube link directly.')
      }
    } catch (err) {
      setGenError(err.message)
    } finally {
      setFindingStreams(false)
    }
  }

  async function handleGenerate(e) {
    e.preventDefault()
    setSubmittingJob(true)
    setGenError(null)
    try {
      const data = await apiFetch('/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          topic,
          clips: Number(clipCount),
          section,
          when,
          brain,
          focus,
          auto_upload_yt: autoYt,
          auto_upload_ig: autoIg,
        }),
      })
      setJobs((prev) => [data.job, ...prev])
    } catch (err) {
      setGenError(err.message)
    } finally {
      setSubmittingJob(false)
    }
  }

  async function handleResumeJob(jobId) {
    try {
      await apiFetch(`/api/jobs/${jobId}/resume`, { method: 'POST' })
      refreshAll()
    } catch (err) {
      setGenError(err.message)
    }
  }

  async function handleYtFileUpload(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setYtBusy(true)
    setYtErr(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const data = await apiFetch('/api/auth/youtube/secret/file', { method: 'POST', body: fd })
      setStatus((prev) => ({ ...prev, youtube: data.youtube }))
    } catch (err) {
      setYtErr(err.message)
    } finally {
      setYtBusy(false)
    }
  }

  async function handleYtSaveKeys(e) {
    e.preventDefault()
    setYtBusy(true)
    setYtErr(null)
    try {
      const data = await apiFetch('/api/auth/youtube/secret', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ client_id: ytClientId, client_secret: ytClientSecret }),
      })
      setStatus((prev) => ({ ...prev, youtube: data.youtube }))
    } catch (err) {
      setYtErr(err.message)
    } finally {
      setYtBusy(false)
    }
  }

  // Poll YouTube OAuth completion while popup authorization is pending
  useEffect(() => {
    if (!showYtModal || !ytAuthUrl) return
    const timer = setInterval(async () => {
      try {
        const auth = await apiFetch('/api/auth/status')
        if (auth.youtube?.connected) {
          setStatus((prev) => ({ ...prev, youtube: auth.youtube }))
          setYtAuthUrl(null)
          setYtBusy(false)
          setShowYtModal(false)
        }
      } catch {
        // ignore transient poll errors
      }
    }, 2000)
    return () => clearInterval(timer)
  }, [showYtModal, ytAuthUrl])

  async function handleYtAuthorize() {
    setYtBusy(true)
    setYtErr(null)
    try {
      const data = await apiFetch('/api/auth/youtube/connect', { method: 'POST' })
      if (data.auth_url) {
        setYtAuthUrl(data.auth_url)
        window.open(data.auth_url, 'yt_oauth', 'width=540,height=680')
      } else if (data.youtube?.connected) {
        setStatus((prev) => ({ ...prev, youtube: data.youtube }))
        setShowYtModal(false)
      }
    } catch (err) {
      setYtErr(err.message)
      setYtBusy(false)
    }
  }

  async function handleYtDisconnect() {
    setYtBusy(true)
    try {
      const data = await apiFetch('/api/auth/youtube/disconnect', { method: 'POST' })
      setStatus((prev) => ({ ...prev, youtube: data.youtube }))
    } finally {
      setYtBusy(false)
    }
  }

  async function handleIgConnect(e) {
    e.preventDefault()
    setIgBusy(true)
    setIgErr(null)
    try {
      const data = await apiFetch('/api/auth/instagram/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: igUser,
          password: igPass,
          verification_code: ig2fa || null,
        }),
      })
      setStatus((prev) => ({ ...prev, instagram: data.instagram }))
      setShowIgModal(false)
      setIgPass('')
      setIg2fa('')
    } catch (err) {
      setIgErr(err.message)
    } finally {
      setIgBusy(false)
    }
  }

  async function handleIgSessionConnect(e) {
    e.preventDefault()
    setIgBusy(true)
    setIgErr(null)
    try {
      const data = await apiFetch('/api/auth/instagram/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: igSessionId,
          username: igUser || null,
        }),
      })
      setStatus((prev) => ({ ...prev, instagram: data.instagram }))
      setShowIgModal(false)
      setIgSessionId('')
    } catch (err) {
      setIgErr(err.message)
    } finally {
      setIgBusy(false)
    }
  }

  async function handleIgDisconnect() {
    setIgBusy(true)
    try {
      const data = await apiFetch('/api/auth/instagram/disconnect', { method: 'POST' })
      setStatus((prev) => ({ ...prev, instagram: data.instagram }))
    } finally {
      setIgBusy(false)
    }
  }

  const creators = useMemo(() => {
    const set = new Set(clips.map((c) => c.creator).filter(Boolean))
    return ['ALL', ...Array.from(set)]
  }, [clips])

  const filteredClips = useMemo(() => {
    return clips.filter((c) => {
      if (creatorFilter !== 'ALL' && c.creator !== creatorFilter) return false
      if (searchText.trim()) {
        const q = searchText.toLowerCase()
        return (
          (c.title || '').toLowerCase().includes(q) ||
          (c.creator || '').toLowerCase().includes(q) ||
          (c.topic || '').toLowerCase().includes(q)
        )
      }
      return true
    })
  }, [clips, creatorFilter, searchText])

  const ytConnected = Boolean(status?.youtube?.connected)
  const igConnected = Boolean(status?.instagram?.connected)

  function resolvedPlatforms() {
    if (schedPlatforms === 'youtube') return ['youtube']
    if (schedPlatforms === 'instagram') return ['instagram']
    const list = []
    if (ytConnected) list.push('youtube')
    if (igConnected) list.push('instagram')
    return list.length ? list : ['youtube', 'instagram']
  }

  async function handleScheduleAll() {
    setSchedBusy(true)
    setSchedMsg(null)
    try {
      const platforms = resolvedPlatforms()
      const data = await apiFetch('/api/schedule', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          clip_ids: filteredClips.map((c) => c.id),
          platforms,
          interval_minutes: Number(schedInterval) || 0,
          start_delay_minutes: Number(schedStartDelay) || 0,
          yt_native_schedule: schedYtNative,
          skip_already_uploaded: schedSkipUploaded,
          privacy: 'public',
        }),
      })
      setSchedule(data.schedule || [])
      setSchedMsg({
        ok: true,
        text: data.added > 0
          ? `Scheduled ${data.added} upload slot(s) across ${platforms.join(' + ')}!`
          : 'No eligible un-uploaded clips matched (uncheck "Skip already-uploaded" to re-post).',
      })
    } catch (err) {
      setSchedMsg({ ok: false, text: err.message })
    } finally {
      setSchedBusy(false)
    }
  }

  async function handleScheduleOne(clip) {
    setSchedMsg(null)
    try {
      const platforms = resolvedPlatforms()
      const data = await apiFetch('/api/schedule', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          clip_ids: [clip.id],
          platforms,
          interval_minutes: Math.max(1, Number(schedInterval) || 15),
          start_delay_minutes: -1,
          yt_native_schedule: schedYtNative,
          skip_already_uploaded: false,
          privacy: 'public',
        }),
      })
      setSchedule(data.schedule || [])
      setSchedMsg({ ok: true, text: `Queued "${clip.title}" into the next schedule slot.` })
    } catch (err) {
      setSchedMsg({ ok: false, text: err.message })
    }
  }

  async function handleCancelSchedule(id) {
    try {
      const data = await apiFetch(`/api/schedule/${id}`, { method: 'DELETE' })
      setSchedule(data.schedule || [])
    } catch (err) {
      setSchedMsg({ ok: false, text: err.message })
    }
  }

  async function handleClearSchedule() {
    try {
      const data = await apiFetch('/api/schedule/clear', { method: 'POST' })
      setSchedule(data.schedule || [])
    } catch (err) {
      setSchedMsg({ ok: false, text: err.message })
    }
  }

  return (
    <div className="studio-shell">
      {/* Top Bar */}
      <header className="topbar">
        <div className="brand">
          <div className="brand-icon">
            <Film size={22} />
          </div>
          <div>
            <h1>StreamClips AI Studio</h1>
            <p>GPU CUDA Clipper + Direct YouTube Shorts & Instagram Reels Uploader</p>
          </div>
        </div>

        <div className="status-pills">
          <div className="pill gpu">
            <Cpu size={15} />
            <span>{status?.gpu?.gpu_name || 'Checking GPU...'} · NVENC</span>
          </div>

          <button
            className={`pill ${ytConnected ? 'connected-yt' : ''}`}
            onClick={() => setShowYtModal(true)}
          >
            <span className={`dot ${ytConnected ? 'on' : ''}`} />
            <Youtube size={16} color="#ef4444" />
            <span>{ytConnected ? `YT: ${status.youtube.channel}` : 'Connect YouTube'}</span>
          </button>

          <button
            className={`pill ${igConnected ? 'connected-ig' : ''}`}
            onClick={() => setShowIgModal(true)}
          >
            <span className={`dot ${igConnected ? 'on' : ''}`} />
            <Instagram size={16} color="#ec4899" />
            <span>{igConnected ? `IG: @${status.instagram.username}` : 'Connect Instagram'}</span>
          </button>

          <button className="pill" onClick={refreshAll} title="Refresh clips & status">
            <RefreshCw size={15} />
          </button>
        </div>
      </header>

      {/* Generator + Live Pipeline */}
      <section className="grid-top">
        <div className="card">
          <div className="card-header">
            <h2><Zap size={18} color="#a78bfa" /> 1-Click Viral Clip Generator</h2>
            <span style={{ fontSize: '0.76rem', color: 'var(--muted)' }}>
              m3u8 Fast Slicer · CUDA Whisper
            </span>
          </div>

          <div className="preset-row">
            <span className="preset-label">Quick pick:</span>
            {STREAMER_PRESETS.map((name) => (
              <button
                type="button"
                key={name}
                className={`chip ${query === name ? 'active' : ''}`}
                onClick={() => setQuery(name)}
              >
                {name}
              </button>
            ))}
          </div>

          <form onSubmit={handleGenerate}>
            <div className="form-grid">
              <div className="field form-full">
                <label>Streamer Name OR Direct YouTube / Twitch / Kick Stream URL</label>
                <input
                  className="input"
                  placeholder="e.g. Kai Cenat, IShowSpeed, or https://www.youtube.com/watch?v=..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  required
                />
              </div>

              <div className="field">
                <label>Game / Topic</label>
                <input
                  className="input"
                  placeholder="e.g. GTA 6, Valorant, Just Chatting"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                />
              </div>

              <div className="field">
                <label>How Many Clips ({clipCount})</label>
                <input
                  className="input"
                  type="number"
                  min={1}
                  max={15}
                  value={clipCount}
                  onChange={(e) => setClipCount(e.target.value)}
                />
              </div>

              <div className="field">
                <label>Time Section (leave blank for full stream)</label>
                <input
                  className="input"
                  placeholder="e.g. 0:20:00-1:00:00"
                  value={section}
                  onChange={(e) => setSection(e.target.value)}
                />
              </div>

              <div className="field">
                <label>Moment Picker Brain</label>
                <select className="select" value={brain} onChange={(e) => setBrain(e.target.value)}>
                  <option value="smart">Hybrid Agent + Smart Auto (1-Click)</option>
                  <option value="agent">Queue for Antigravity Agent in Chat</option>
                </select>
              </div>

              <div className="field form-full">
                <label>Extra Focus (optional)</label>
                <input
                  className="input"
                  placeholder="e.g. funniest NPC reactions, rage moments, police chases"
                  value={focus}
                  onChange={(e) => setFocus(e.target.value)}
                />
              </div>
            </div>

            <div className="toggle-row">
              <label className="check-label">
                <input
                  type="checkbox"
                  checked={autoYt}
                  disabled={!ytConnected}
                  onChange={(e) => setAutoYt(e.target.checked)}
                />
                Auto-upload to YouTube Shorts
              </label>

              <label className="check-label">
                <input
                  type="checkbox"
                  checked={autoIg}
                  disabled={!igConnected}
                  onChange={(e) => setAutoIg(e.target.checked)}
                />
                Auto-upload to Instagram Reels
              </label>
            </div>

            {genError && <div className="alert alert-err" style={{ marginTop: 12 }}>{genError}</div>}

            <div className="action-row">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleFindStreams}
                disabled={findingStreams}
              >
                {findingStreams ? <Loader2 size={15} className="spin" /> : <Search size={15} />}
                Find Streams
              </button>

              <button type="submit" className="btn btn-primary" disabled={submittingJob}>
                {submittingJob ? <Loader2 size={16} className="spin" /> : <Sparkles size={16} />}
                1-Click Generate {clipCount} Best Clips
              </button>
            </div>
          </form>

          {foundStreams.length > 0 && (
            <div className="found-list">
              {foundStreams.map((s) => (
                <div className="found-item" key={s.url}>
                  <div>
                    <strong>{s.name}</strong>: {s.title}
                    <div className="found-meta">
                      {(s.views || 0).toLocaleString()} views · {Math.round((s.seconds || 0) / 60)} min
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => {
                      setQuery(s.url)
                      setFoundStreams([])
                    }}
                  >
                    <Play size={13} /> Use URL
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Live Jobs */}
        <div className="card">
          <div className="card-header">
            <h2><Bot size={18} color="#34d399" /> Active & Recent Jobs</h2>
            <span style={{ fontSize: '0.76rem', color: 'var(--muted)' }}>
              {jobs.length} total
            </span>
          </div>

          <div className="jobs-list">
            {jobs.length === 0 ? (
              <p style={{ color: 'var(--muted)', fontSize: '0.86rem' }}>
                No clipping jobs started from the web UI yet. Pick a streamer on the left and click
                <strong> 1-Click Generate</strong> to start!
              </p>
            ) : (
              jobs.map((job) => (
                <div className="job-box" key={job.id}>
                  <div className="job-top">
                    <span className="job-title">
                      {job.params?.query} · {job.params?.topic} ({job.params?.clips} clips)
                    </span>
                    <span className={`badge badge-${job.status}`}>{job.step || job.status}</span>
                  </div>
                  {job.status === 'waiting_for_agent' && (
                    <div style={{ marginTop: 6, marginBottom: 6 }}>
                      <span style={{ fontSize: '0.78rem', color: '#fcd34d' }}>
                        Queued {job.waiting_prompts?.length || 0} transcript prompt(s) for Antigravity Agent.
                        Ask me in chat to pick them, or click Resume once answered.
                      </span>
                      <div style={{ marginTop: 6 }}>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleResumeJob(job.id)}
                        >
                          Resume Job
                        </button>
                      </div>
                    </div>
                  )}
                  {job.error && (
                    <div className="alert alert-err" style={{ marginTop: 6, marginBottom: 6 }}>
                      {job.error}
                    </div>
                  )}
                  {job.logs?.length > 0 && (
                    <div className="job-logs">
                      {job.logs.slice(-14).map((l) => l.line).join('\n')}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </section>

      {/* 1-Click Upload All & Drip Scheduler */}
      <section className="scheduler-card">
        <div className="card-header">
          <h2><CalendarClock size={18} color="#f472b6" /> 1-Click Upload All &amp; Drip Scheduler</h2>
          <span style={{ fontSize: '0.76rem', color: 'var(--muted)' }}>
            Works for YouTube Shorts (Cloud publishAt or Drip) &amp; Instagram Reels (Background Drip)
          </span>
        </div>

        <div className="scheduler-grid">
          <div className="field">
            <label>Upload Target</label>
            <select
              className="select"
              value={schedPlatforms}
              onChange={(e) => setSchedPlatforms(e.target.value)}
            >
              <option value="both">Both (YouTube Shorts + Instagram Reels)</option>
              <option value="youtube">YouTube Shorts Only</option>
              <option value="instagram">Instagram Reels Only</option>
            </select>
          </div>

          <div className="field">
            <label>Interval Between Uploads (mins)</label>
            <div className="interval-chips">
              {INTERVAL_PRESETS.map((p) => (
                <button
                  type="button"
                  key={p.value}
                  className={`chip ${Number(schedInterval) === p.value ? 'active' : ''}`}
                  onClick={() => setSchedInterval(p.value)}
                >
                  {p.label}
                </button>
              ))}
              <input
                type="number"
                className="input"
                style={{ width: 78, padding: '5px 8px', fontSize: '0.8rem' }}
                min={0}
                max={1440}
                value={schedInterval}
                onChange={(e) => setSchedInterval(e.target.value)}
                title="Custom minutes"
              />
            </div>
          </div>

          <div className="field">
            <label>Start First Upload</label>
            <select
              className="select"
              value={schedStartDelay}
              onChange={(e) => setSchedStartDelay(Number(e.target.value))}
            >
              <option value={0}>Immediately (Now)</option>
              <option value={15}>In 15 minutes</option>
              <option value={30}>In 30 minutes</option>
              <option value={60}>In 1 hour</option>
            </select>
          </div>

          <div>
            <button
              type="button"
              className="btn btn-primary"
              style={{ width: '100%' }}
              disabled={schedBusy || filteredClips.length === 0 || (!ytConnected && !igConnected)}
              onClick={handleScheduleAll}
              title={!ytConnected && !igConnected ? 'Connect YouTube or Instagram first' : ''}
            >
              {schedBusy ? <Loader2 size={16} className="spin" /> : <Upload size={16} />}
              {Number(schedInterval) === 0
                ? `1-Click Upload All (${filteredClips.length} Clips)`
                : `1-Click Schedule All (${filteredClips.length} Clips)`}
            </button>
          </div>
        </div>

        <div className="toggle-row" style={{ marginTop: 12, paddingTop: 10 }}>
          <label className="check-label">
            <input
              type="checkbox"
              checked={schedSkipUploaded}
              onChange={(e) => setSchedSkipUploaded(e.target.checked)}
            />
            Skip already-uploaded clips
          </label>

          <label className="check-label">
            <input
              type="checkbox"
              checked={schedYtNative}
              onChange={(e) => setSchedYtNative(e.target.checked)}
            />
            YouTube Cloud Schedule (`publishAt` — uploads privately now &amp; auto-publishes even if PC is off)
          </label>
        </div>

        {schedMsg && (
          <div className={`alert ${schedMsg.ok ? 'alert-ok' : 'alert-err'}`} style={{ marginTop: 12, marginBottom: 0 }}>
            {schedMsg.text}
          </div>
        )}

        {schedule.length > 0 && (
          <div className="sched-queue">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
              <strong style={{ fontSize: '0.84rem' }}>
                Scheduled Uploads Queue ({schedule.length})
              </strong>
              <button type="button" className="btn btn-secondary btn-sm" onClick={handleClearSchedule}>
                <Trash2 size={13} /> Clear Finished
              </button>
            </div>

            {schedule.map((item) => (
              <div className="sched-item" key={item.id}>
                <div className="sched-left">
                  <strong>{item.clip_title}</strong>
                  <span className="found-meta">
                    {item.creator} ·{' '}
                    {item.yt_publish_at
                      ? `YT Cloud Publish: ${new Date(item.publish_display_at || item.scheduled_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
                      : `Scheduled: ${new Date(item.scheduled_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} (${formatCountdown(item.scheduled_ts)})`}
                  </span>
                  {item.error && <span style={{ color: '#fca5a5', fontSize: '0.74rem' }}>{item.error}</span>}
                </div>

                <div className="sched-right">
                  {item.platforms?.includes('youtube') && (
                    <span className="platform-pill platform-yt">
                      {item.yt_publish_at ? 'YT Cloud' : 'YT Short'}
                    </span>
                  )}
                  {item.platforms?.includes('instagram') && (
                    <span className="platform-pill platform-ig">IG Reel</span>
                  )}
                  <span className={`badge badge-${item.status}`}>{item.status}</span>
                  {item.status === 'scheduled' && (
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => handleCancelSchedule(item.id)}
                      title="Cancel scheduled upload"
                    >
                      <X size={13} />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Clips Library */}
      <section>
        <div className="library-bar">
          <div>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700 }}>
              Generated Clips Studio ({filteredClips.length})
            </h2>
            <p style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>
              Preview clips, tweak catchy titles, and upload straight to YouTube Shorts & Instagram Reels.
            </p>
          </div>

          <div className="filter-pills">
            {creators.map((cr) => (
              <button
                key={cr}
                className={`chip ${creatorFilter === cr ? 'active' : ''}`}
                onClick={() => setCreatorFilter(cr)}
              >
                {cr}
              </button>
            ))}
            <input
              className="input"
              style={{ width: 210, padding: '6px 12px' }}
              placeholder="Search titles..."
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
            />
          </div>
        </div>

        <div className="clips-grid">
          {filteredClips.map((clip) => (
            <ClipCard
              key={clip.id}
              clip={clip}
              ytConnected={ytConnected}
              igConnected={igConnected}
              schedInterval={Number(schedInterval) || 15}
              onSaved={(updated) => {
                setClips((prev) => prev.map((c) => (c.id === updated.id ? updated : c)))
              }}
              onUploaded={(updated) => {
                setClips((prev) => prev.map((c) => (c.id === updated.id ? updated : c)))
              }}
              onScheduleOne={handleScheduleOne}
            />
          ))}
        </div>
      </section>

      {/* YouTube Connection Modal */}
      {showYtModal && (
        <div className="modal-backdrop" onClick={() => { setShowYtModal(false); setYtBusy(false); setYtAuthUrl(null) }}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3><Youtube size={20} color="#ef4444" /> Connect YouTube Shorts</h3>
              <button className="pill" onClick={() => { setShowYtModal(false); setYtBusy(false); setYtAuthUrl(null) }}><X size={15} /></button>
            </div>
            <p className="modal-sub">
              Uses official Google OAuth 2.0 to upload vertical #Shorts directly to your YouTube channel.
            </p>

            {ytErr && <div className="alert alert-err">{ytErr}</div>}

            {ytConnected ? (
              <div>
                <div className="alert alert-ok">
                  Connected as <strong>{status.youtube.channel}</strong>
                </div>
                <button className="btn btn-yt" style={{ width: '100%' }} onClick={handleYtDisconnect} disabled={ytBusy}>
                  Disconnect YouTube
                </button>
              </div>
            ) : (
              <>
                <div className="field" style={{ marginBottom: 14 }}>
                  <label>Step 1a: Upload Google Cloud Desktop OAuth `client_secret.json`</label>
                  <input className="input" type="file" accept=".json" onChange={handleYtFileUpload} />
                </div>

                <form onSubmit={handleYtSaveKeys} style={{ marginBottom: 14 }}>
                  <div className="field" style={{ marginBottom: 8 }}>
                    <label>Or Step 1b: Paste OAuth Client ID & Secret</label>
                    <input
                      className="input"
                      placeholder="Client ID (...apps.googleusercontent.com)"
                      value={ytClientId}
                      onChange={(e) => setYtClientId(e.target.value)}
                    />
                  </div>
                  <div className="field" style={{ marginBottom: 8 }}>
                    <input
                      className="input"
                      type="password"
                      placeholder="Client Secret"
                      value={ytClientSecret}
                      onChange={(e) => setYtClientSecret(e.target.value)}
                    />
                  </div>
                  <button className="btn btn-secondary btn-sm" type="submit" disabled={ytBusy || !ytClientId || !ytClientSecret}>
                    Save OAuth Credentials
                  </button>
                </form>

                <button
                  className="btn btn-primary"
                  style={{ width: '100%' }}
                  onClick={handleYtAuthorize}
                  disabled={ytBusy || !status?.youtube?.has_secret}
                >
                  {ytBusy ? <Loader2 size={16} className="spin" /> : <Youtube size={16} />}
                  {ytAuthUrl ? 'Waiting for Google Sign-In...' : 'Step 2: Authorize in Browser'}
                </button>
                {ytAuthUrl && (
                  <div className="alert alert-ok" style={{ marginTop: 10, marginBottom: 0 }}>
                    Popup opened! If your browser blocked it,{' '}
                    <a
                      href={ytAuthUrl}
                      target="_blank"
                      rel="noreferrer"
                      style={{ color: '#fff', textDecoration: 'underline', fontWeight: 600 }}
                    >
                      click here to open Google Sign-In
                    </a>
                    .
                  </div>
                )}
                {!status?.youtube?.has_secret && (
                  <p style={{ fontSize: '0.75rem', color: 'var(--muted)', marginTop: 8 }}>
                    Upload `client_secret.json` or save Client ID & Secret first to enable browser authorization.
                  </p>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* Instagram Connection Modal */}
      {showIgModal && (
        <div className="modal-backdrop" onClick={() => setShowIgModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3><Instagram size={20} color="#ec4899" /> Connect Instagram Reels</h3>
              <button className="pill" onClick={() => setShowIgModal(false)}><X size={15} /></button>
            </div>
            <p className="modal-sub">
              Signs into your Instagram account and stores an encrypted session locally in `~/.streamclips`.
            </p>

            {igErr && <div className="alert alert-err">{igErr}</div>}

            {igConnected ? (
              <div>
                <div className="alert alert-ok">
                  Connected as <strong>@{status.instagram.username}</strong>
                </div>
                <button className="btn btn-ig" style={{ width: '100%' }} onClick={handleIgDisconnect} disabled={igBusy}>
                  Disconnect Instagram
                </button>
              </div>
            ) : (
              <>
                <div className="preset-row" style={{ marginBottom: 14 }}>
                  <button
                    type="button"
                    className={`chip ${igMode === 'password' ? 'active' : ''}`}
                    onClick={() => { setIgMode('password'); setIgErr(null) }}
                  >
                    Username &amp; Password
                  </button>
                  <button
                    type="button"
                    className={`chip ${igMode === 'session' ? 'active' : ''}`}
                    onClick={() => { setIgMode('session'); setIgErr(null) }}
                  >
                    Session ID Cookie (Recommended)
                  </button>
                </div>

                {igMode === 'password' ? (
                  <form onSubmit={handleIgConnect}>
                    <div className="field" style={{ marginBottom: 10 }}>
                      <label>Instagram Username</label>
                      <input
                        className="input"
                        placeholder="username"
                        value={igUser}
                        onChange={(e) => setIgUser(e.target.value)}
                        required
                      />
                    </div>
                    <div className="field" style={{ marginBottom: 10 }}>
                      <label>Password</label>
                      <input
                        className="input"
                        type="password"
                        placeholder="••••••••"
                        value={igPass}
                        onChange={(e) => setIgPass(e.target.value)}
                        required
                      />
                    </div>
                    <div className="field" style={{ marginBottom: 14 }}>
                      <label>2FA Verification Code (optional, if enabled)</label>
                      <input
                        className="input"
                        placeholder="6-digit code"
                        value={ig2fa}
                        onChange={(e) => setIg2fa(e.target.value)}
                      />
                    </div>
                    <button className="btn btn-primary" style={{ width: '100%' }} type="submit" disabled={igBusy}>
                      {igBusy ? <Loader2 size={16} className="spin" /> : <Instagram size={16} />}
                      Connect Instagram Account
                    </button>
                  </form>
                ) : (
                  <form onSubmit={handleIgSessionConnect}>
                    <p style={{ fontSize: '0.77rem', color: 'var(--muted)', marginBottom: 12 }}>
                      1. Log into <strong>instagram.com</strong> in Chrome/Edge.<br />
                      2. Press <strong>F12</strong> → <strong>Application</strong> → <strong>Cookies</strong> → <code>https://www.instagram.com</code>.<br />
                      3. Copy the value of <code>sessionid</code> and paste it below.
                    </p>
                    <div className="field" style={{ marginBottom: 10 }}>
                      <label>Instagram `sessionid` Cookie</label>
                      <input
                        className="input"
                        type="password"
                        placeholder="Paste sessionid cookie value..."
                        value={igSessionId}
                        onChange={(e) => setIgSessionId(e.target.value)}
                        required
                      />
                    </div>
                    <div className="field" style={{ marginBottom: 14 }}>
                      <label>Username (optional, auto-detected if blank)</label>
                      <input
                        className="input"
                        placeholder="e.g. gta6hubclypz"
                        value={igUser}
                        onChange={(e) => setIgUser(e.target.value)}
                      />
                    </div>
                    <button className="btn btn-primary" style={{ width: '100%' }} type="submit" disabled={igBusy}>
                      {igBusy ? <Loader2 size={16} className="spin" /> : <Instagram size={16} />}
                      Connect via Session Cookie
                    </button>
                  </form>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
