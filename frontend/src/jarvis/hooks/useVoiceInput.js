import { useCallback, useMemo } from 'react'

import { useMicRecorder } from './useMicRecorder'
import { useSpeechRecognition } from './useSpeechRecognition'

/**
 * Best-effort voice: Chrome/Edge live speech (fast, accurate) → Groq Whisper fallback.
 */
export function useVoiceInput({ onTranscript, onError }) {
  const onBrowserResult = useCallback(
    (text) => {
      if (text?.trim()) onTranscript?.(text.trim())
    },
    [onTranscript],
  )

  const onBrowserError = useCallback(
    (code) => {
      if (code === 'network' || code === 'service-not-available') {
        onError?.('speech-network')
        return
      }
      onError?.(code)
    },
    [onError],
  )

  const speech = useSpeechRecognition({
    onResult: onBrowserResult,
    onError: onBrowserError,
    autoStopOnSilence: false,
  })

  const mic = useMicRecorder({
    onTranscript,
    onError,
  })

  const mode = speech.supported ? 'browser' : 'whisper'

  const recording = mode === 'browser' ? speech.listening : mic.recording
  const transcribing = mode === 'browser' ? false : mic.transcribing
  const interim = mode === 'browser' ? speech.interim : mic.preview
  const level = mic.level
  const supported = mode === 'browser' ? speech.supported : mic.supported

  const startListening = useCallback(() => {
    if (mode === 'browser') speech.start()
    else mic.startListening()
  }, [mode, speech, mic])

  const stopListening = useCallback(() => {
    if (mode === 'browser') speech.stop()
    else mic.stopListening()
  }, [mode, speech, mic])

  const toggleListening = useCallback(() => {
    if (recording) stopListening()
    else if (!transcribing) startListening()
  }, [recording, transcribing, startListening, stopListening])

  return useMemo(
    () => ({
      mode,
      recording,
      transcribing,
      interim,
      level,
      supported,
      startListening,
      stopListening,
      toggleListening,
    }),
    [
      mode,
      recording,
      transcribing,
      interim,
      level,
      supported,
      startListening,
      stopListening,
      toggleListening,
    ],
  )
}
