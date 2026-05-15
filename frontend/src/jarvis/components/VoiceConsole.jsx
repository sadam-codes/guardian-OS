import { useCallback, useEffect, useState } from 'react'
import { fetchJarvisCapabilities, sendJarvisCommand } from '../api/jarvis'
import { useSpeechRecognition } from '../hooks/useSpeechRecognition'
import { useToast } from '../../components/ToastProvider'

const SPEECH_ERRORS = {
  'not-allowed': 'Microphone blocked. Allow mic access in browser settings, then try again.',
  'no-speech': 'No speech detected. Hold the mic button and speak clearly.',
  'audio-capture': 'No microphone found. Connect a mic and try again.',
  'network': 'Speech needs internet in Chrome. Check your connection.',
  'aborted': '',
  start_failed: 'Could not start microphone. Click the mic again.',
  already_started: 'Already listening. Wait a moment and try again.',
}

export default function VoiceConsole({ userName }) {
  const toast = useToast()
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [assistantName, setAssistantName] = useState('Guardian')
  const [examples, setExamples] = useState([])
  const [history, setHistory] = useState([])

  useEffect(() => {
    fetchJarvisCapabilities()
      .then((data) => {
        setAssistantName(data.assistant_name || 'Guardian')
        setExamples(data.examples || [])
      })
      .catch(() => {})
  }, [])

  const runCommand = useCallback(
    async (commandText) => {
      const trimmed = commandText.trim()
      if (!trimmed || busy) return
      setBusy(true)
      setText('')
      try {
        const res = await sendJarvisCommand(trimmed, userName)
        setHistory((prev) => [
          { id: Date.now(), input: trimmed, output: res.message, success: res.success, intent: res.intent },
          ...prev.slice(0, 19),
        ])
        if (res.success) toast.success(res.message)
        else toast.error(res.message)
        if ('speechSynthesis' in window) {
          window.speechSynthesis.cancel()
          const utter = new SpeechSynthesisUtterance(res.message)
          utter.rate = 1
          window.speechSynthesis.speak(utter)
        }
      } catch (err) {
        toast.error(err.message || 'Command failed')
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

  const { listening, supported, interim, start, stop, ensureMicPermission } = useSpeechRecognition({
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

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-indigo-100 bg-gradient-to-br from-indigo-50 via-white to-slate-50 p-6 shadow-sm">
        <div className="flex flex-col items-center text-center">
          <button
            type="button"
            onClick={toggleMic}
            disabled={!supported}
            className={`relative flex h-28 w-28 cursor-pointer items-center justify-center rounded-full border-4 transition ${
              listening
                ? 'border-indigo-500 bg-indigo-600 text-white shadow-lg shadow-indigo-300/50'
                : 'border-slate-200 bg-white text-indigo-600 shadow-md hover:border-indigo-300 hover:bg-indigo-50'
            } disabled:cursor-not-allowed disabled:opacity-50`}
          >
            {listening && (
              <span className="absolute inset-0 animate-ping rounded-full bg-indigo-400/30" />
            )}
            <MicIcon className="relative h-10 w-10" />
          </button>
          <p className="mt-4 text-lg font-semibold text-slate-900">
            {listening ? 'Listening… speak now' : busy ? 'Working…' : `Talk to ${assistantName}`}
          </p>
          <p className="mt-1 max-w-md text-sm text-slate-500">
            {supported
              ? 'Click the mic, wait for “Listening”, then say your command. Works best in Chrome or Edge.'
              : 'Speech is not supported here — use Chrome or Edge, or type commands below.'}
          </p>
          {(interim || (listening && text)) && (
            <p className="mt-2 text-sm italic text-indigo-600">{interim || text}</p>
          )}
        </div>
      </div>

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
          placeholder='Or type: "open chrome", "what time is it"'
          className="flex-1 rounded-xl border border-slate-200 bg-white px-4 py-3 text-slate-900 shadow-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20"
        />
        <button
          type="submit"
          disabled={busy || !text.trim()}
          className="cursor-pointer rounded-xl bg-indigo-600 px-5 py-3 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Run
        </button>
      </form>

      {examples.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Try saying</p>
          <div className="flex flex-wrap gap-2">
            {examples.map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => runCommand(ex)}
                disabled={busy}
                className="cursor-pointer rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600 hover:border-indigo-200 hover:text-indigo-700 disabled:opacity-50"
              >
                {ex}
              </button>
            ))}
          </div>
        </div>
      )}

      {history.length > 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold text-slate-900">Recent commands</h3>
          <ul className="max-h-64 space-y-2 overflow-y-auto">
            {history.map((item) => (
              <li key={item.id} className="rounded-lg bg-slate-50 px-3 py-2 text-sm">
                <p className="font-medium text-slate-800">You: {item.input}</p>
                <p className={item.success ? 'text-emerald-700' : 'text-red-600'}>
                  {assistantName}: {item.output}
                </p>
                <p className="text-xs text-slate-400">{item.intent}</p>
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
