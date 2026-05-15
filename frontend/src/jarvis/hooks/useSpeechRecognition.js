import { useCallback, useEffect, useRef, useState } from 'react'

export function useSpeechRecognition({ onResult, onError, lang = 'en-US' } = {}) {
  const [listening, setListening] = useState(false)
  const [supported, setSupported] = useState(false)
  const [interim, setInterim] = useState('')
  const recognitionRef = useRef(null)
  const onResultRef = useRef(onResult)
  const onErrorRef = useRef(onError)
  const pendingTextRef = useRef('')

  useEffect(() => {
    onResultRef.current = onResult
  }, [onResult])

  useEffect(() => {
    onErrorRef.current = onError
  }, [onError])

  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    setSupported(Boolean(SpeechRecognition))
    if (!SpeechRecognition) return undefined

    const recognition = new SpeechRecognition()
    recognition.lang = lang
    recognition.continuous = true
    recognition.interimResults = true
    recognition.maxAlternatives = 1

    recognition.onstart = () => {
      setListening(true)
      setInterim('')
      pendingTextRef.current = ''
    }

    recognition.onresult = (event) => {
      let finalText = ''
      let interimText = ''
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const part = event.results[i][0].transcript
        if (event.results[i].isFinal) finalText += part
        else interimText += part
      }
      const combined = (finalText || interimText).trim()
      if (combined) pendingTextRef.current = combined
      setInterim(interimText || (finalText ? '' : combined))
      if (finalText.trim()) {
        onResultRef.current?.(finalText.trim())
        pendingTextRef.current = ''
        setInterim('')
        try {
          recognition.stop()
        } catch {
          /* ignore */
        }
      }
    }

    recognition.onerror = (event) => {
      setListening(false)
      const code = event.error || 'speech_error'
      if (code !== 'aborted') onErrorRef.current?.(code)
    }

    recognition.onend = () => {
      setListening(false)
      const leftover = pendingTextRef.current.trim()
      if (leftover) {
        onResultRef.current?.(leftover)
        pendingTextRef.current = ''
        setInterim('')
      }
    }

    recognitionRef.current = recognition
    return () => {
      try {
        recognition.abort()
      } catch {
        /* ignore */
      }
      recognitionRef.current = null
    }
  }, [lang])

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
    if (!recognitionRef.current || listening) return
    const allowed = await ensureMicPermission()
    if (!allowed) return
    try {
      recognitionRef.current.start()
    } catch (err) {
      if (err?.message?.includes('already started')) {
        try {
          recognitionRef.current.stop()
          recognitionRef.current.start()
        } catch {
          onErrorRef.current?.('already_started')
        }
      } else {
        onErrorRef.current?.('start_failed')
      }
    }
  }, [listening, ensureMicPermission])

  const stop = useCallback(() => {
    try {
      recognitionRef.current?.stop()
    } catch {
      /* ignore */
    }
  }, [])

  return { listening, supported, interim, start, stop, ensureMicPermission }
}
