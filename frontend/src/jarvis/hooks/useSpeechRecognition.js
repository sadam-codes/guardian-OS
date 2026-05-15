import { useCallback, useEffect, useRef, useState } from 'react'

/** Pause this long after last heard words → treat as end of command. */
const SILENCE_MS = 1600
/** Restart mic after no-speech / end if user left listening on. */
const RESTART_MS = 400

function resolveSpeechLang() {
  const nav = (navigator.language || 'en-US').toLowerCase()
  if (nav.startsWith('ur')) return 'ur-PK'
  if (nav.startsWith('en')) return nav.includes('pk') ? 'en-PK' : 'en-US'
  return 'en-US'
}

export function useSpeechRecognition({ onResult, onError, lang } = {}) {
  const [listening, setListening] = useState(false)
  const [supported, setSupported] = useState(false)
  const [interim, setInterim] = useState('')
  const recognitionRef = useRef(null)
  const onResultRef = useRef(onResult)
  const onErrorRef = useRef(onError)
  const pendingTextRef = useRef('')
  const activeRef = useRef(false)
  const silenceTimerRef = useRef(null)
  const restartTimerRef = useRef(null)
  const finalizedRef = useRef(false)
  const speechLang = lang || resolveSpeechLang()

  useEffect(() => {
    onResultRef.current = onResult
  }, [onResult])

  useEffect(() => {
    onErrorRef.current = onError
  }, [onError])

  const clearSilenceTimer = useCallback(() => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current)
      silenceTimerRef.current = null
    }
  }, [])

  const clearRestartTimer = useCallback(() => {
    if (restartTimerRef.current) {
      clearTimeout(restartTimerRef.current)
      restartTimerRef.current = null
    }
  }, [])

  const finalizePending = useCallback(
    (text) => {
      const trimmed = (text || pendingTextRef.current).trim()
      if (!trimmed || finalizedRef.current) return
      finalizedRef.current = true
      pendingTextRef.current = ''
      setInterim('')
      clearSilenceTimer()
      clearRestartTimer()
      activeRef.current = false
      onResultRef.current?.(trimmed)
    },
    [clearSilenceTimer, clearRestartTimer],
  )

  const scheduleSilenceFinalize = useCallback(() => {
    clearSilenceTimer()
    silenceTimerRef.current = setTimeout(() => {
      finalizePending()
    }, SILENCE_MS)
  }, [clearSilenceTimer, finalizePending])

  const startRecognition = useCallback(() => {
    const recognition = recognitionRef.current
    if (!recognition || !activeRef.current) return
    finalizedRef.current = false
    try {
      recognition.start()
    } catch (err) {
      if (String(err?.message || err).includes('already started')) {
        try {
          recognition.stop()
          setTimeout(() => {
            if (activeRef.current) {
              try {
                recognition.start()
              } catch {
                onErrorRef.current?.('start_failed')
              }
            }
          }, 200)
        } catch {
          onErrorRef.current?.('already_started')
        }
      } else {
        onErrorRef.current?.('start_failed')
      }
    }
  }, [])

  const scheduleRestart = useCallback(() => {
    clearRestartTimer()
    if (!activeRef.current) return
    restartTimerRef.current = setTimeout(() => {
      if (activeRef.current) startRecognition()
    }, RESTART_MS)
  }, [clearRestartTimer, startRecognition])

  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    setSupported(Boolean(SpeechRecognition))
    if (!SpeechRecognition) return undefined

    const recognition = new SpeechRecognition()
    recognition.lang = speechLang
    // Single-utterance mode is far more reliable in Chrome/Edge than continuous.
    recognition.continuous = false
    recognition.interimResults = true
    recognition.maxAlternatives = 1

    recognition.onstart = () => {
      setListening(true)
      finalizedRef.current = false
    }

    recognition.onresult = (event) => {
      let finalText = ''
      let interimText = ''
      for (let i = 0; i < event.results.length; i += 1) {
        const part = event.results[i][0].transcript
        if (event.results[i].isFinal) finalText += part
        else interimText += part
      }

      const live = (finalText + interimText).trim()
      if (live) {
        pendingTextRef.current = live
        setInterim(live)
        scheduleSilenceFinalize()
      }

      if (finalText.trim()) {
        clearSilenceTimer()
        finalizePending(finalText.trim())
        try {
          recognition.stop()
        } catch {
          /* ignore */
        }
      }
    }

    recognition.onerror = (event) => {
      const code = event.error || 'speech_error'
      if (code === 'no-speech') {
        const leftover = pendingTextRef.current.trim()
        if (leftover) {
          finalizePending(leftover)
        } else if (activeRef.current) {
          scheduleRestart()
        }
        return
      }
      if (code === 'aborted') return
      setListening(false)
      onErrorRef.current?.(code)
      if (activeRef.current && code === 'network') {
        activeRef.current = false
      }
    }

    recognition.onend = () => {
      setListening(false)
      if (!finalizedRef.current) {
        const leftover = pendingTextRef.current.trim()
        if (leftover) {
          finalizePending(leftover)
        }
      }
      if (activeRef.current) {
        scheduleRestart()
      }
    }

    recognitionRef.current = recognition
    return () => {
      activeRef.current = false
      clearSilenceTimer()
      clearRestartTimer()
      try {
        recognition.abort()
      } catch {
        /* ignore */
      }
      recognitionRef.current = null
    }
  }, [
    speechLang,
    clearSilenceTimer,
    clearRestartTimer,
    finalizePending,
    scheduleSilenceFinalize,
    scheduleRestart,
    startRecognition,
  ])

  const ensureMicPermission = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) return true
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      stream.getTracks().forEach((t) => t.stop())
      return true
    } catch {
      onErrorRef.current?.('not-allowed')
      return false
    }
  }, [])

  const start = useCallback(async () => {
    if (!recognitionRef.current) return
    if (activeRef.current) return
    const allowed = await ensureMicPermission()
    if (!allowed) return
    activeRef.current = true
    pendingTextRef.current = ''
    setInterim('')
    finalizedRef.current = false
    startRecognition()
  }, [ensureMicPermission, startRecognition])

  const stop = useCallback(() => {
    activeRef.current = false
    clearSilenceTimer()
    clearRestartTimer()
    const leftover = pendingTextRef.current.trim()
    if (leftover && !finalizedRef.current) {
      finalizePending(leftover)
    }
    try {
      recognitionRef.current?.stop()
    } catch {
      /* ignore */
    }
    setListening(false)
    setInterim('')
  }, [clearSilenceTimer, clearRestartTimer, finalizePending])

  return { listening, supported, interim, start, stop, ensureMicPermission, speechLang }
}
