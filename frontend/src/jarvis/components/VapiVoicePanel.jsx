import { useCallback, useEffect, useRef, useState } from 'react'
import Vapi from '@vapi-ai/web'
import { isVapiConfigured, VAPI_ASSISTANT_ID, VAPI_PUBLIC_KEY } from '../config/vapi'
import { useVapiCall } from '../context/VapiCallContext'
import { speakBrowser } from '../utils/speak'

/** flux-* needs browser input processors Chrome may not support — use nova-2 for web. */
const WEB_TRANSCRIBER = {
  provider: 'deepgram',
  model: import.meta.env.VITE_VAPI_TRANSCRIBER_MODEL || 'nova-2',
  language: 'en',
}

function cancelBrowserSpeech() {
  if ('speechSynthesis' in window) window.speechSynthesis.cancel()
}

function formatInitError(err) {
  const msg = err?.message || String(err)
  if (/cannot find module|failed to resolve|@vapi-ai\/web/i.test(msg)) {
    return 'Vapi SDK missing. In the frontend folder run: npm install @vapi-ai/web — then restart npm run dev.'
  }
  return `Vapi failed to load: ${msg}`
}

/**
 * Vapi voice (mic + TTS via Vapi). Browser TTS fallback if Vapi audio is silent.
 * No ElevenLabs API key required.
 */
export default function VapiVoicePanel({ userName, assistantName = 'Guardian' }) {
  const vapiRef = useRef(null)
  const { registerClient, setCallActive } = useVapiCall() || {}
  const [ready, setReady] = useState(false)
  const [active, setActive] = useState(false)
  const [status, setStatus] = useState('Loading Vapi…')
  const [lastLine, setLastLine] = useState('')
  const [toolStatus, setToolStatus] = useState('')
  const [volume, setVolume] = useState(0)
  const [fallbackMode, setFallbackMode] = useState('')
  const volumeRef = useRef(0)
  const assistantSpokeRef = useRef(false)
  const fallbackTimerRef = useRef(null)
  const pendingTextRef = useRef('')

  const configured = isVapiConfigured()

  const scheduleBrowserFallback = useCallback((text) => {
    pendingTextRef.current = text
    if (fallbackTimerRef.current) clearTimeout(fallbackTimerRef.current)
    fallbackTimerRef.current = setTimeout(() => {
      if (assistantSpokeRef.current) return
      const line = pendingTextRef.current
      if (!line) return
      speakBrowser(line)
      setFallbackMode('Browser voice')
    }, 2000)
  }, [])

  useEffect(() => {
    if (!configured) return undefined

    try {
      const VapiClass = Vapi?.default ?? Vapi
      if (typeof VapiClass !== 'function') {
        throw new Error('Invalid @vapi-ai/web export (not a constructor).')
      }

      const client = new VapiClass(
        VAPI_PUBLIC_KEY,
        undefined,
        { alwaysIncludeMicInPermissionPrompt: true },
        { startAudioOff: false },
      )

      client.on('call-start', () => {
        cancelBrowserSpeech()
        setActive(true)
        setCallActive?.(true)
        setStatus('Listening…')
        setToolStatus('')
        setFallbackMode('')
        assistantSpokeRef.current = false
        try {
          client.setMuted(false)
        } catch {
          /* ignore */
        }
      })

      client.on('call-start-success', () => {
        setStatus('Connected — speak now')
      })

      client.on('call-start-failed', (ev) => {
        const err = ev?.error || ev?.message || 'Call could not start'
        setStatus(typeof err === 'string' ? err : 'Call failed to start')
        setActive(false)
        setCallActive?.(false)
      })

      client.on('call-end', () => {
        setActive(false)
        setCallActive?.(false)
        setStatus('Tap to talk with Vapi')
        setVolume(0)
      })

      client.on('volume-level', (level) => {
        const n = typeof level === 'number' ? level : 0
        volumeRef.current = n
        setVolume(n)
        if (n > 0.05) {
          assistantSpokeRef.current = true
          if (fallbackTimerRef.current) {
            clearTimeout(fallbackTimerRef.current)
            fallbackTimerRef.current = null
          }
          setFallbackMode('')
        }
      })

      client.on('message', (message) => {
        if (message?.type === 'transcript' && message.transcript) {
          const who = message.role === 'user' ? 'You' : assistantName
          setLastLine(`${who}: ${message.transcript}`)
          if (message.role === 'assistant' && message.transcript?.trim()) {
            scheduleBrowserFallback(message.transcript.trim())
          }
        }
        if (message?.type === 'function-call' && message.functionCall?.name) {
          setToolStatus('Running on your PC…')
        }
        if (message?.type === 'function-call-result') {
          setToolStatus('')
        }
      })

      client.on('speech-start', () => {
        assistantSpokeRef.current = true
        if (fallbackTimerRef.current) {
          clearTimeout(fallbackTimerRef.current)
          fallbackTimerRef.current = null
        }
        setStatus(`${assistantName} speaking…`)
        setFallbackMode('')
      })

      client.on('speech-end', () => {
        setStatus('Listening…')
      })

      client.on('error', (e) => {
        setStatus(e?.message || e?.error?.message || 'Vapi error')
        setActive(false)
        setCallActive?.(false)
      })

      vapiRef.current = client
      registerClient?.(client)
      setReady(true)
      setStatus('Tap to talk with Vapi')
    } catch (err) {
      console.error('Vapi init failed:', err)
      setReady(false)
      setStatus(formatInitError(err))
    }

    return () => {
      if (fallbackTimerRef.current) clearTimeout(fallbackTimerRef.current)
      vapiRef.current?.stop?.()
      vapiRef.current = null
      registerClient?.(null)
      setCallActive?.(false)
    }
  }, [configured, assistantName, registerClient, setCallActive, scheduleBrowserFallback])

  const toggleCall = useCallback(async () => {
    const vapi = vapiRef.current
    if (!vapi) return
    if (active) {
      await vapi.stop()
      return
    }
    cancelBrowserSpeech()
    setStatus('Connecting…')
    setFallbackMode('')
    try {
      await vapi.start(VAPI_ASSISTANT_ID, {
        transcriber: WEB_TRANSCRIBER,
        variableValues: userName ? { userName, user_name: userName } : {},
      })
    } catch (err) {
      console.error('Vapi start failed:', err)
      setStatus(err?.message || 'Could not start Vapi call')
      setActive(false)
      setCallActive?.(false)
    }
  }, [active, userName, setCallActive])

  if (!configured) {
    return (
      <p className="mb-4 max-w-md text-center text-xs text-amber-400/90">
        Vapi voice is not configured. Set VITE_VAPI_PUBLIC_KEY and VITE_VAPI_ASSISTANT_ID in
        frontend .env, then restart npm run dev.
      </p>
    )
  }

  const orbClass = active
    ? 'bg-gradient-to-br from-violet-500/50 to-slate-900 shadow-[0_0_80px_rgba(139,92,246,0.5)]'
    : 'bg-gradient-to-br from-violet-500/15 to-slate-900 shadow-[0_0_40px_rgba(139,92,246,0.2)] hover:shadow-[0_0_60px_rgba(139,92,246,0.35)]'

  return (
    <div className="mb-6 flex w-full max-w-md flex-col items-center text-center">
      <p className="mb-4 text-xs font-medium tracking-wide text-violet-400 uppercase">
        Vapi voice
      </p>

      <div className="relative mb-5 flex items-center justify-center">
        <span
          className={`absolute h-28 w-28 rounded-full bg-violet-500/10 blur-xl transition-opacity ${
            active ? 'opacity-100' : 'opacity-70'
          }`}
        />
        <button
          type="button"
          onClick={toggleCall}
          disabled={!ready}
          title={active ? 'End call' : 'Start Vapi voice'}
          className={`relative z-10 flex h-24 w-24 cursor-pointer items-center justify-center rounded-full border border-white/10 bg-[#0d1219] transition-all duration-300 disabled:cursor-not-allowed disabled:opacity-40 ${orbClass}`}
        >
          <VoiceOrbIcon
            className={`relative h-11 w-11 drop-shadow-[0_0_12px_rgba(167,139,250,0.55)] ${
              active ? 'text-white' : 'text-violet-400'
            }`}
          />
        </button>
      </div>

      {active && volume > 0.05 && (
        <div className="mb-3 h-1 w-32 overflow-hidden rounded-full bg-white/10">
          <div
            className="h-full rounded-full bg-violet-400 transition-all duration-100"
            style={{ width: `${Math.min(100, volume * 100)}%` }}
          />
        </div>
      )}

      <p className="max-w-sm text-sm font-medium text-violet-300">{status}</p>
      {toolStatus && <p className="mt-1 text-xs text-cyan-400/80">{toolStatus}</p>}
      {lastLine && (
        <p className="mt-3 max-w-sm text-center text-sm text-slate-400">&ldquo;{lastLine}&rdquo;</p>
      )}
      {fallbackMode && (
        <p className="mt-2 text-[11px] text-slate-500">
          Vapi audio quiet — also speaking via {fallbackMode.toLowerCase()}.
        </p>
      )}
      {!active && ready && (
        <p className="mt-2 text-[11px] text-slate-500">
          Voice via Vapi (ElevenLabs in Vapi Dashboard). Browser backs up if silent.
        </p>
      )}
    </div>
  )
}

function VoiceOrbIcon({ className }) {
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
