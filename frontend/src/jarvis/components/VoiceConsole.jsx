import { useCallback, useEffect, useState } from 'react'
import { fetchJarvisCapabilities, planJarvisCommand, sendJarvisCommand } from '../api/jarvis'
import { fetchFrequentCommands } from '../api/guardianWorkflow'
import { isVapiConfigured } from '../config/vapi'
import { useVapiCall } from '../context/VapiCallContext'
import { useVoiceInput } from '../hooks/useVoiceInput'
import { speakBrowser } from '../utils/speak'
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

function speakAloud(text, { delayMs = 0, queue = false } = {}) {
  if (!('speechSynthesis' in window) || !text?.trim()) return
  if (!queue) window.speechSynthesis.cancel()
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

function normalizeForCompare(s) {
  return (s || '').trim().toLowerCase().replace(/[.!?]+$/g, '')
}

const VOICE_ERRORS = {
  'not-allowed':
    'Microphone blocked. Click the lock icon in the address bar, allow Microphone, then refresh.',
  'no-speech': 'Did not catch words. Tap mic and say the full command clearly, then pause.',
  'no-audio': 'No audio captured. Check Windows Sound settings and pick the correct input mic.',
  'too-short': 'Too quick. Speak your full command, then pause 1?2 seconds.',
  'too-quiet': 'Mic too quiet. Speak closer and louder; the bar should move.',
  'audio-capture': 'No microphone found. Plug in or enable a mic in Windows settings.',
  record_failed: 'Could not record audio. Try Chrome or Edge.',
  transcribe_failed: 'Could not transcribe. Check GROQ_API_KEY in backend .env.',
  'speech-network': 'Live speech needs internet. Check connection or try again.',
  network: 'Speech service unavailable. Check internet connection.',
}

const QUICK_EXAMPLES = 4

export default function VoiceConsole({
  userName,
  userId,
  identityVerified = true,
  runWorkflow,
  assistantLabel,
  /** When true, no browser mic/TTS — use VapiVoicePanel for voice instead. */
  useVapiVoice = isVapiConfigured(),
}) {
  const toast = useToast()
  const vapiCall = useVapiCall()
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [assistantName, setAssistantName] = useState(assistantLabel || 'Guardian')
  const [examples, setExamples] = useState([])
  const [showAllExamples, setShowAllExamples] = useState(false)
  const [history, setHistory] = useState([])
  const [lastReply, setLastReply] = useState(null)
  const [sessionContext, setSessionContext] = useState(null)
  const [showHistory, setShowHistory] = useState(false)

  useEffect(() => {
    if (assistantLabel) setAssistantName(assistantLabel)
  }, [assistantLabel])

  useEffect(() => {
    fetchJarvisCapabilities()
      .then((data) => {
        setAssistantName(data.assistant_name || assistantLabel || 'Guardian')
        setExamples(data.examples || [])
      })
      .catch(() => {})
    if (userId || userName) {
      fetchFrequentCommands(userId, userName)
        .then((d) => {
          if (d.commands?.length) {
            setExamples((prev) => [...new Set([...d.commands, ...prev])].slice(0, 12))
          }
        })
        .catch(() => {})
    }
  }, [userId, userName, assistantLabel])

  useEffect(() => {
    if (useVapiVoice || !('speechSynthesis' in window)) return
    const load = () => pickFemaleEnglishVoice()
    load()
    window.speechSynthesis.addEventListener('voiceschanged', load)
    return () => window.speechSynthesis.removeEventListener('voiceschanged', load)
  }, [useVapiVoice])

  const runCommand = useCallback(
    async (commandText) => {
      const trimmed = commandText.trim()
      if (!trimmed || busy) return
      setBusy(true)
      setText('')
      let earlyAck = ''
      try {
        let plan = null
        try {
          plan = await planJarvisCommand(trimmed, userName, sessionContext)
          if (plan?.context?.active) setSessionContext(plan.context)
          earlyAck = (plan.jarvis_brief || plan.understood || '').trim()
          if (earlyAck) {
            const viaVapi = useVapiVoice && vapiCall?.active && vapiCall?.speak?.(earlyAck)
            if (!viaVapi && useVapiVoice) speakBrowser(earlyAck)
            else if (!useVapiVoice) speakAloud(earlyAck, { delayMs: 0 })
          }
        } catch {
          plan = null
        }

        const res = runWorkflow
          ? await runWorkflow({ text: trimmed, context: sessionContext, plan })
          : await sendJarvisCommand(trimmed, userName, sessionContext, plan)
        if (res.context) setSessionContext(res.context?.active ? res.context : null)
        const entry = {
          id: Date.now(),
          input: trimmed,
          output: res.message,
          success: res.success,
          intent: res.intent,
          blocked: res.security_blocked,
        }
        setHistory((prev) => [entry, ...prev.slice(0, 14)])
        setLastReply(entry)

        const finalMsg = (res.message || '').trim()
        const speakLine = finalMsg || earlyAck
        if (speakLine) {
          const viaVapi =
            useVapiVoice && vapiCall?.active && vapiCall?.speak?.(speakLine)
          if (!viaVapi) {
            if (useVapiVoice) {
              speakBrowser(speakLine)
            } else if (finalMsg && normalizeForCompare(finalMsg) !== normalizeForCompare(earlyAck)) {
              speakAloud(finalMsg, { delayMs: earlyAck ? 300 : 200, queue: Boolean(earlyAck) })
            } else if (!earlyAck && finalMsg) {
              speakAloud(finalMsg, { delayMs: 200 })
            } else if (earlyAck) {
              speakAloud(earlyAck, { delayMs: 0 })
            }
          }
        }
      } catch (err) {
        toast.error(err.message || 'Could not reach server')
      } finally {
        setBusy(false)
      }
    },
    [busy, toast, userName, sessionContext, runWorkflow, useVapiVoice, vapiCall],
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

  const micBlocked = !useVapiVoice && !supported
  const micBusy = !useVapiVoice && (recording || transcribing)

  const onMicClick = () => {
    if (useVapiVoice) return
    if (busy && !recording && !transcribing) {
      toast.error('Wait for the current command to finish.')
      return
    }
    if (transcribing) return
    toggleListening()
  }

  const visibleExamples = showAllExamples ? examples : examples.slice(0, QUICK_EXAMPLES)
  const statusLabel = transcribing
    ? 'Processing?'
    : recording
      ? 'Listening'
      : busy
        ? 'Executing'
        : 'Tap to speak'

  const orbClass = recording
    ? 'bg-gradient-to-br from-cyan-500/50 to-slate-900 shadow-[0_0_80px_rgba(6,182,212,0.5)]'
    : transcribing
      ? 'bg-gradient-to-br from-amber-500/30 to-slate-900 shadow-[0_0_50px_rgba(251,191,36,0.3)]'
      : busy
        ? 'animate-pulse bg-gradient-to-br from-cyan-500/25 to-slate-900 shadow-[0_0_40px_rgba(6,182,212,0.2)]'
        : 'bg-gradient-to-br from-cyan-500/15 to-slate-900 shadow-[0_0_40px_rgba(6,182,212,0.15)] hover:shadow-[0_0_60px_rgba(6,182,212,0.25)]'

  return (
    <div className="flex w-full max-w-md flex-col items-center text-center">
      {!useVapiVoice && (
      <>
      <div className="relative mb-5 flex items-center justify-center">
        <span
          className={`absolute h-28 w-28 rounded-full bg-cyan-500/10 blur-xl transition-opacity ${
            recording ? 'opacity-100' : 'opacity-70'
          }`}
        />
        <button
          type="button"
          onClick={onMicClick}
          disabled={micBlocked || transcribing || (busy && !recording)}
          title={recording ? 'Tap to stop and send' : 'Tap to speak'}
          className={`relative z-10 flex h-24 w-24 cursor-pointer items-center justify-center rounded-full border border-white/10 bg-[#0d1219] transition-all duration-300 disabled:cursor-not-allowed disabled:opacity-40 ${orbClass}`}
        >
          <MicIcon
            className={`relative h-11 w-11 drop-shadow-[0_0_12px_rgba(34,211,238,0.55)] ${
              recording ? 'text-white' : 'text-cyan-400'
            }`}
          />
        </button>
      </div>

      <p className="text-sm font-medium text-cyan-400">{statusLabel}</p>
      {mode === 'browser' && !micBusy && (
        <p className="mt-1 text-xs text-slate-500">Live speech enabled</p>
      )}

      {recording && interim && (
        <p className="mb-4 max-w-sm text-center text-sm text-cyan-200/80">
          &ldquo;{interim}&rdquo;
        </p>
      )}

      {recording && mode === 'whisper' && (
        <div className="mb-4 w-full max-w-xs">
          <div className="h-0.5 overflow-hidden rounded-full bg-white/5">
            <div
              className="h-full rounded-full bg-gradient-to-r from-cyan-600 to-cyan-400 transition-all duration-75"
              style={{ width: `${Math.max(8, level)}%` }}
            />
          </div>
        </div>
      )}
      </>
      )}

      {useVapiVoice && (
        <p className="mb-4 text-xs text-slate-500">
          {vapiCall?.active
            ? 'Typed commands use Vapi or browser voice.'
            : 'Start the purple Vapi mic above, or type — browser will speak replies.'}
        </p>
      )}

      {lastReply && !micBusy && !busy && (
        <div
          className={`mb-5 max-w-md rounded-lg border px-4 py-2.5 text-center text-sm ${
            lastReply.success
              ? 'border-cyan-500/20 bg-cyan-500/5 text-cyan-100/90'
              : 'border-red-500/20 bg-red-500/5 text-red-300/90'
          }`}
        >
          {lastReply.output}
        </div>
      )}

      {micBlocked && !useVapiVoice && (
        <p className="mb-4 text-center text-xs text-red-400/80">
          Mic unavailable — use Chrome or Edge
        </p>
      )}

      <form
        className={`flex w-full gap-2 ${useVapiVoice ? 'mt-2' : 'mt-8'}`}
        onSubmit={(e) => {
          e.preventDefault()
          runCommand(text)
        }}
      >
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Command?"
          className="min-w-0 flex-1 rounded-xl border border-white/10 bg-[#0a0e14] px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500 outline-none focus:border-cyan-500/40 focus:ring-1 focus:ring-cyan-500/25"
        />
        <button
          type="submit"
          disabled={busy || !text.trim()}
          className="shrink-0 cursor-pointer rounded-xl bg-cyan-500 px-5 py-3 text-sm font-semibold text-white shadow-[0_0_20px_rgba(6,182,212,0.25)] hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Run
        </button>
      </form>



      {/* recent ? toggle */}
      {history.length > 0 && (
        <div className="mt-4 w-full">
          <button
            type="button"
            onClick={() => setShowHistory((v) => !v)}
            className="cursor-pointer text-xs text-slate-400 hover:text-slate-200"
          >
            {showHistory ? 'Hide' : 'Show'} recent ({history.length})
          </button>
          {showHistory && (
            <ul className="mt-2 max-h-28 space-y-1 overflow-y-auto">
              {history.map((item) => (
                <li
                  key={item.id}
                  className="rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2 text-[11px]"
                >
                  <p className="truncate text-slate-500">{item.input}</p>
                  <p className={`truncate ${item.success ? 'text-cyan-500/70' : 'text-red-400/70'}`}>
                    {item.output}
                  </p>
                </li>
              ))}
            </ul>
          )}
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
