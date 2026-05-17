import { useCallback, useEffect, useRef, useState } from 'react'

/** After you stop talking, wait this long then send the command. */
const SILENCE_MS = 1500
/** Max time with no words before we warn / stop. */
const NO_SPEECH_GIVE_UP_MS = 12000

function cancelAssistantSpeech() {
  if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel()
  }
}

export function useSpeechRecognition({
  onResult,
  onError,
  lang = 'en-US',
  autoStopOnSilence = false,
} = {}) {
  const [listening, setListening] = useState(false)
  const [supported, setSupported] = useState(false)
  const [interim, setInterim] = useState('')
  const [hearing, setHearing] = useState(false)
  const [micError, setMicError] = useState(null)

  const recognitionRef = useRef(null)
  const onResultRef = useRef(onResult)
  const onErrorRef = useRef(onError)
  const pendingTextRef = useRef('')
  const activeRef = useRef(false)
  const silenceTimerRef = useRef(null)
  const noSpeechTimerRef = useRef(null)
  const finalizedRef = useRef(false)
  const speechLang = lang

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

  const clearNoSpeechTimer = useCallback(() => {
    if (noSpeechTimerRef.current) {
      clearTimeout(noSpeechTimerRef.current)
      noSpeechTimerRef.current = null
    }
  }, [])

  const reportError = useCallback((code) => {
    setMicError(code)
    onErrorRef.current?.(code)
  }, [])

  const finalizeRef = useRef(() => {})

  finalizeRef.current = () => {
    const trimmed = pendingTextRef.current.trim()
    if (!trimmed || finalizedRef.current) {
      return
    }
    finalizedRef.current = true
    activeRef.current = false
    pendingTextRef.current = ''
    setInterim('')
    clearSilenceTimer()
    clearNoSpeechTimer()
    try {
      recognitionRef.current?.stop()
    } catch {
      /* ignore */
    }
    setListening(false)
    setHearing(false)
    setMicError(null)
    onResultRef.current?.(trimmed)
  }

  const scheduleFinalizeAfterSilenceRef = useRef(() => {})
  scheduleFinalizeAfterSilenceRef.current = () => {
    clearSilenceTimer()
    silenceTimerRef.current = setTimeout(() => {
      finalizeRef.current()
    }, SILENCE_MS)
  }

  const armNoSpeechTimeoutRef = useRef(() => {})
  armNoSpeechTimeoutRef.current = () => {
    clearNoSpeechTimer()
    noSpeechTimerRef.current = setTimeout(() => {
      if (!activeRef.current) return
      if (!pendingTextRef.current.trim()) {
        activeRef.current = false
        try {
          recognitionRef.current?.stop()
        } catch {
          /* ignore */
        }
        setListening(false)
        setHearing(false)
        reportError('no-speech')
      }
    }, NO_SPEECH_GIVE_UP_MS)
  }

  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    setSupported(Boolean(SpeechRecognition))
    if (!SpeechRecognition) return undefined

    const recognition = new SpeechRecognition()
    recognition.lang = speechLang
    recognition.continuous = true
    recognition.interimResults = true
    recognition.maxAlternatives = 1

    recognition.onstart = () => {
      setListening(true)
      setMicError(null)
      finalizedRef.current = false
      armNoSpeechTimeoutRef.current()
    }

    recognition.onsoundstart = () => {
      setHearing(true)
      setMicError(null)
    }

    recognition.onsoundend = () => {
      setHearing(false)
    }

    recognition.onspeechstart = () => {
      setHearing(true)
      clearNoSpeechTimer()
    }

    recognition.onresult = (event) => {
      let finalText = ''
      let interimText = ''
      for (let i = 0; i < event.results.length; i += 1) {
        const part = event.results[i][0].transcript
        if (event.results[i].isFinal) finalText += part
        else interimText += part
      }
      const combined = (finalText + interimText).trim()
      if (!combined) return

      pendingTextRef.current = combined
      setInterim(combined)
      setHearing(true)
      setMicError(null)
      clearNoSpeechTimer()
      if (autoStopOnSilence) {
        scheduleFinalizeAfterSilenceRef.current()
      }
    }

    recognition.onerror = (event) => {
      const code = event.error || 'speech_error'
      if (code === 'aborted') return

      if (code === 'no-speech') {
        if (pendingTextRef.current.trim()) {
          finalizeRef.current()
        }
        return
      }

      setListening(false)
      setHearing(false)
      activeRef.current = false

      if (code === 'not-allowed') {
        reportError('not-allowed')
        return
      }
      if (code === 'network' || code === 'service-not-available') {
        reportError('network')
        return
      }
      if (code === 'audio-capture') {
        reportError('audio-capture')
        return
      }
      reportError(code)
    }

    recognition.onend = () => {
      setListening(false)
      setHearing(false)
      if (activeRef.current && !finalizedRef.current) {
        const leftover = pendingTextRef.current.trim()
        if (leftover) {
          finalizeRef.current()
          return
        }
        try {
          recognition.start()
        } catch {
          activeRef.current = false
          reportError('start_failed')
        }
      }
    }

    recognitionRef.current = recognition
    return () => {
      activeRef.current = false
      clearSilenceTimer()
      clearNoSpeechTimer()
      try {
        recognition.abort()
      } catch {
        /* ignore */
      }
      recognitionRef.current = null
    }
  }, [speechLang, autoStopOnSilence, clearSilenceTimer, clearNoSpeechTimer, reportError])

  const start = useCallback(() => {
    const recognition = recognitionRef.current
    if (!recognition) return
    if (activeRef.current) return

    cancelAssistantSpeech()
    setMicError(null)
    activeRef.current = true
    pendingTextRef.current = ''
    setInterim('')
    setHearing(false)
    finalizedRef.current = false

    try {
      recognition.start()
    } catch (err) {
      const msg = String(err?.message || err)
      if (msg.includes('already started')) {
        try {
          recognition.stop()
        } catch {
          /* ignore */
        }
        setTimeout(() => {
          if (!activeRef.current) return
          try {
            recognitionRef.current?.start()
          } catch {
            activeRef.current = false
            reportError('start_failed')
          }
        }, 300)
      } else {
        activeRef.current = false
        reportError('start_failed')
      }
    }
  }, [reportError])

  const stop = useCallback(() => {
    activeRef.current = false
    clearSilenceTimer()
    clearNoSpeechTimer()
    const leftover = pendingTextRef.current.trim()
    if (leftover && !finalizedRef.current) {
      finalizedRef.current = true
      pendingTextRef.current = ''
      setInterim('')
      setListening(false)
      setHearing(false)
      try {
        recognitionRef.current?.stop()
      } catch {
        /* ignore */
      }
      onResultRef.current?.(leftover)
      return
    }
    try {
      recognitionRef.current?.stop()
    } catch {
      /* ignore */
    }
    setListening(false)
    setHearing(false)
    setInterim('')
  }, [clearSilenceTimer, clearNoSpeechTimer])

  return {
    listening,
    supported,
    interim,
    hearing,
    micError,
    start,
    stop,
    speechLang,
  }
}
