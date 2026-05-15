import { useCallback, useEffect, useState } from 'react'
import { fetchJarvisCapabilities, sendJarvisCommand } from '../api/jarvis'
import { useSpeechRecognition } from '../hooks/useSpeechRecognition'
import { useToast } from '../../components/ToastProvider'

function pickMaleEnglishVoice() {
  if (!('speechSynthesis' in window)) return null
  const voices = window.speechSynthesis.getVoices()
  if (!voices.length) return null
  const prefer = (v) =>
    v.lang.toLowerCase().startsWith('en') &&
    /male|david|guy|daniel|mark|ryan|james|google uk english male|microsoft.*male/i.test(
      `${v.name} ${v.voiceURI}`,
    )
  return voices.find(prefer) || voices.find((v) => v.lang.toLowerCase().startsWith('en')) || voices[0]
}

function speakAloud(text) {
  if (!('speechSynthesis' in window) || !text?.trim()) return
  window.speechSynthesis.cancel()
  const utter = new SpeechSynthesisUtterance(text)
  const voice = pickMaleEnglishVoice()
  if (voice) utter.voice = voice
  utter.rate = 0.95
  utter.pitch = 0.92
  window.speechSynthesis.speak(utter)
}

const SPEECH_ERRORS = {
  'not-allowed': 'Microphone blocked. Allow mic access in browser settings.',
  'no-speech': 'No speech heard. Speak clearly, then pause briefly.',
  'audio-capture': 'No microphone found.',
  network: 'Speech needs internet (Chrome/Edge).',
  aborted: '',
  start_failed: 'Could not start mic. Click again.',
  already_started: 'Already listening.',
}

const QUICK_EXAMPLES = 6

export default function VoiceConsole({ userName }) {
  const toast = useToast()
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [assistantName, setAssistantName] = useState('Guardian')
  const [examples, setExamples] = useState([])
  const [showAllExamples, setShowAllExamples] = useState(false)
  const [history, setHistory] = useState([])
  const [lastReply, setLastReply] = useState(null)

  useEffect(() => {
    fetchJarvisCapabilities()
      .then((data) => {
        setAssistantName(data.assistant_name || 'Guardian')
        setExamples(data.examples || [])
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!('speechSynthesis' in window)) return
    const load = () => pickMaleEnglishVoice()
    load()
    window.speechSynthesis.addEventListener('voiceschanged', load)
    return () => window.speechSynthesis.removeEventListener('voiceschanged', load)
  }, [])

  const runCommand = useCallback(
    async (commandText) => {
      const trimmed = commandText.trim()
      if (!trimmed || busy) return
      setBusy(true)
      setText('')
      try {
        const res = await sendJarvisCommand(trimmed, userName)
        const entry = {
          id: Date.now(),
          input: trimmed,
          output: res.message,
          success: res.success,
          intent: res.intent,
        }
        setHistory((prev) => [entry, ...prev.slice(0, 14)])
        setLastReply(entry)
        speakAloud(res.message)
      } catch (err) {
        toast.error(err.message || 'Could not reach server')
      } finally {
        setBusy(false)
      }
    },
    [busy, toast, userName],
  )

  const onVoiceResult = useCallback(
    (spoken) => {
      if (!spoken?.trim()) return
      setText(spoken)
      runCommand(spoken)
    },
    [runCommand],
  )

  const onSpeechError = useCallback(
    (code) => {
      const msg = SPEECH_ERRORS[code]
      if (msg) toast.error(msg)
    },
    [toast],
  )

  const { listening, supported, interim, start, stop, ensureMicPermission, speechLang } =
    useSpeechRecognition({
      onResult: onVoiceResult,
      onError: onSpeechError,
    })

  useEffect(() => {
    if (supported) ensureMicPermission().catch(() => {})
  }, [supported, ensureMicPermission])

  const toggleMic = async () => {
    if (listening) {
      stop()
      return
    }
    if (busy) {
      toast.error('Wait for the current command to finish.')
      return
    }
    await start()
  }

  const visibleExamples = showAllExamples ? examples : examples.slice(0, QUICK_EXAMPLES)
  const statusLabel = listening ? 'Listening…' : busy ? 'Working…' : `Talk to ${assistantName}`

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-100 px-4 py-3 sm:px-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-base font-semibold text-slate-900">Voice assistant</h2>
            <p className="text-xs text-slate-500">Speak or type · {speechLang} · Chrome/Edge</p>
          </div>
          {history.length > 0 && (
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
              {history.length} recent
            </span>
          )}
        </div>
      </div>

      <div className="grid gap-4 p-4 sm:p-5 lg:grid-cols-[auto_1fr] lg:gap-5">
        <div className="flex flex-col items-center lg:items-start">
          <button
            type="button"
            onClick={toggleMic}
            disabled={!supported}
            className={`relative flex h-20 w-20 shrink-0 cursor-pointer items-center justify-center rounded-full border-[3px] transition ${
              listening
                ? 'border-indigo-500 bg-indigo-600 text-white shadow-md shadow-indigo-300/40'
                : 'border-slate-200 bg-slate-50 text-indigo-600 hover:border-indigo-300 hover:bg-indigo-50'
            } disabled:cursor-not-allowed disabled:opacity-50`}
          >
            {listening && (
              <span className="absolute inset-0 animate-ping rounded-full bg-indigo-400/25" />
            )}
            <MicIcon className="relative h-8 w-8" />
          </button>
          <p className="mt-2 text-sm font-medium text-slate-900">{statusLabel}</p>
          {listening && !interim && (
            <p className="mt-0.5 text-xs text-amber-600">Speak, then pause ~1s</p>
          )}
          {(interim || (listening && text)) && (
            <p className="mt-1 max-w-[220px] text-center text-sm font-medium text-indigo-700 lg:text-left">
              {interim || text}
            </p>
          )}
          {lastReply && !listening && !busy && (
            <div
              className={`mt-2 max-w-xs rounded-lg border px-2.5 py-2 text-left text-xs ${
                lastReply.success
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-900'
                  : 'border-red-200 bg-red-50 text-red-900'
              }`}
            >
              <p className="font-medium">{assistantName}</p>
              <p className="mt-0.5 leading-snug">{lastReply.output}</p>
            </div>
          )}
        </div>

        <div className="min-w-0 space-y-3">
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault()
              runCommand(text)
            }}
          >
            <input
              type="text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder='e.g. "open chrome", "what time is it"'
              className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 outline-none focus:border-indigo-500 focus:bg-white focus:ring-2 focus:ring-indigo-500/15"
            />
            <button
              type="submit"
              disabled={busy || !text.trim()}
              className="shrink-0 cursor-pointer rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Run
            </button>
          </form>

          {examples.length > 0 && (
            <div>
              <div className="mb-1.5 flex items-center justify-between gap-2">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                  Quick commands
                </p>
                {examples.length > QUICK_EXAMPLES && (
                  <button
                    type="button"
                    onClick={() => setShowAllExamples((v) => !v)}
                    className="cursor-pointer text-[11px] font-medium text-indigo-600 hover:text-indigo-800"
                  >
                    {showAllExamples ? 'Show less' : `+${examples.length - QUICK_EXAMPLES} more`}
                  </button>
                )}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {visibleExamples.map((ex) => (
                  <button
                    key={ex}
                    type="button"
                    onClick={() => runCommand(ex)}
                    disabled={busy}
                    className="cursor-pointer rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] leading-tight text-slate-600 hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-800 disabled:opacity-50"
                  >
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {history.length > 0 && (
        <div className="border-t border-slate-100 px-4 py-3 sm:px-5">
          <h3 className="mb-2 text-xs font-semibold text-slate-700">Recent</h3>
          <ul className="max-h-40 space-y-1.5 overflow-y-auto pr-1">
            {history.map((item) => (
              <li
                key={item.id}
                className="rounded-md border border-slate-100 bg-slate-50/80 px-2.5 py-1.5 text-xs"
              >
                <p className="truncate font-medium text-slate-800">You: {item.input}</p>
                <p className={`truncate ${item.success ? 'text-emerald-700' : 'text-red-600'}`}>
                  {assistantName}: {item.output}
                </p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function MicIcon({ className }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z"
      />
    </svg>
  )
}
