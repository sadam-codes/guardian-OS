import { useCallback, useEffect, useState } from 'react'
import { fetchJarvisCapabilities, sendJarvisCommand } from '../api/jarvis'
import { useVoiceInput } from '../hooks/useVoiceInput'
import { useToast } from '../../components/ToastProvider'

function pickFemaleEnglishVoice() {
  if (!('speechSynthesis' in window)) return null
  const voices = window.speechSynthesis.getVoices()
  if (!voices.length) return null

  const isEnglish = (v) => v.lang.toLowerCase().startsWith('en')
  const label = (v) => `${v.name} ${v.voiceURI}`.toLowerCase()
  const isMale = (v) =>
    /male|david|guy|daniel|mark|ryan|james|george|brian|eric|steven|richard|andrew/i.test(
      label(v),
    )
  const isFemale = (v) =>
    isEnglish(v) &&
    !isMale(v) &&
    /female|zira|jenny|samantha|susan|linda|karen|aria|emma|hazel|natasha|laura|joanna|kimberly|salli|sonia|veena|michelle|helen|lily/i.test(
      label(v),
    )

  return (
    voices.find(isFemale) ||
    voices.find((v) => isEnglish(v) && !isMale(v)) ||
    voices.find(isEnglish) ||
    voices[0]
  )
}

function speakAloud(text, { delayMs = 0 } = {}) {
  if (!('speechSynthesis' in window) || !text?.trim()) return
  window.speechSynthesis.cancel()
  const run = () => {
    const utter = new SpeechSynthesisUtterance(text)
    const voice = pickFemaleEnglishVoice()
    if (voice) utter.voice = voice
    utter.rate = 0.96
    utter.pitch = 1.05
    window.speechSynthesis.speak(utter)
  }
  if (delayMs > 0) setTimeout(run, delayMs)
  else run()
}

const VOICE_ERRORS = {
  'not-allowed':
    'Microphone blocked. Click the lock icon in the address bar, allow Microphone, then refresh.',
  'no-speech': 'Did not catch words. Tap mic and say the full command clearly, then pause.',
  'no-audio': 'No audio captured. Check Windows Sound settings and pick the correct input mic.',
  'too-short': 'Too quick. Speak your full command, then pause 1–2 seconds.',
  'too-quiet': 'Mic too quiet. Speak closer and louder; the red bar should move.',
  'audio-capture': 'No microphone found. Plug in or enable a mic in Windows settings.',
  record_failed: 'Could not record audio. Try Chrome or Edge.',
  transcribe_failed: 'Could not transcribe. Check GROQ_API_KEY in backend .env.',
  'speech-network': 'Live speech needs internet. Check connection or try again.',
  network: 'Speech service unavailable. Check internet connection.',
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
  const [sessionContext, setSessionContext] = useState(null)
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
    const load = () => pickFemaleEnglishVoice()
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
        const res = await sendJarvisCommand(trimmed, userName, sessionContext)
        if (res.context) setSessionContext(res.context?.active ? res.context : null)
        const entry = {
          id: Date.now(),
          input: trimmed,
          output: res.message,
          success: res.success,
          intent: res.intent,
        }
        setHistory((prev) => [entry, ...prev.slice(0, 14)])
        setLastReply(entry)
        speakAloud(res.message, { delayMs: 400 })
      } catch (err) {
        toast.error(err.message || 'Could not reach server')
      } finally {
        setBusy(false)
      }
    },
    [busy, toast, userName, sessionContext],
  )

  const onVoiceResult = useCallback(
    (spoken) => {
      if (!spoken?.trim()) return
      window.speechSynthesis?.cancel()
      runCommand(spoken)
    },
    [runCommand],
  )

  const onVoiceError = useCallback(
    (codeOrMsg) => {
      const msg = VOICE_ERRORS[codeOrMsg] || codeOrMsg
      if (msg) toast.error(msg)
    },
    [toast],
  )

  const { recording, transcribing, supported, level, interim, mode, toggleListening } =
    useVoiceInput({
      onTranscript: onVoiceResult,
      onError: onVoiceError,
    })

  const micBlocked = !supported
  const micBusy = recording || transcribing

  const onMicClick = () => {
    if (busy && !recording && !transcribing) {
      toast.error('Wait for the current command to finish.')
      return
    }
    if (transcribing) return
    toggleListening()
  }

  const visibleExamples = showAllExamples ? examples : examples.slice(0, QUICK_EXAMPLES)
  const statusLabel = transcribing
    ? 'Understanding…'
    : recording
      ? 'Listening… tap mic again to stop & send'
      : busy
        ? 'Working…'
        : `Talk to ${assistantName}`

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-100 px-4 py-3 sm:px-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-base font-semibold text-slate-900">Voice assistant</h2>
            <p className="text-xs text-slate-500">
              Tap mic to start · tap again to stop & send
              {mode === 'browser' && (
                <span className="ml-1 text-emerald-600">· live speech</span>
              )}
              {sessionContext?.active && (
                <span className="ml-1 text-indigo-600">· follow-up on</span>
              )}
            </p>
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
            onClick={onMicClick}
            disabled={micBlocked || transcribing || (busy && !recording)}
            title={
              micBlocked
                ? 'Voice needs Chrome or Edge'
                : recording
                  ? 'Tap to stop and send'
                  : transcribing
                    ? 'Processing your voice…'
                    : 'Tap to start listening'
            }
            className={`relative flex h-20 w-20 shrink-0 cursor-pointer items-center justify-center rounded-full border-[3px] transition ${
              recording
                ? 'border-red-500 bg-red-600 text-white shadow-md shadow-red-300/40'
                : transcribing
                  ? 'border-amber-400 bg-amber-500 text-white'
                  : 'border-slate-200 bg-slate-50 text-indigo-600 hover:border-indigo-300 hover:bg-indigo-50'
            } disabled:cursor-not-allowed disabled:opacity-50`}
          >
            {recording && (
              <span className="absolute inset-0 animate-ping rounded-full bg-red-400/30" />
            )}
            <MicIcon className="relative h-8 w-8" />
          </button>
          <p className="mt-2 text-sm font-medium text-slate-900">{statusLabel}</p>
          {micBlocked && (
            <p className="mt-1 max-w-[220px] text-center text-xs text-red-600 lg:text-left">
              Mic unavailable — use Chrome or Edge (not Firefox).
            </p>
          )}
          {recording && interim && (
            <p className="mt-2 max-w-xs text-center text-sm font-medium text-indigo-800 lg:text-left">
              &ldquo;{interim}&rdquo;
            </p>
          )}
          {recording && mode === 'whisper' && (
            <div className="mt-2 w-full max-w-[220px]">
              <div className="h-1.5 overflow-hidden rounded-full bg-slate-200">
                <div
                  className="h-full rounded-full bg-red-500 transition-all duration-75"
                  style={{ width: `${Math.max(8, level)}%` }}
                />
              </div>
              <p className="mt-1 text-center text-xs text-red-600 lg:text-left">
                {level > 8 ? 'Mic is picking up sound' : 'Speak louder - red bar should move'}
              </p>
            </div>
          )}
          {lastReply && !micBusy && !busy && (
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
