import { useCallback, useEffect, useRef, useState } from 'react'

import { transcribeJarvisAudio } from '../api/jarvis'

const MAX_RECORD_MS = 60000
const MIN_RECORD_MS = 1200
const MIN_BLOB_BYTES = 500
const TIMESLICE_MS = 200
const SILENCE_MS = 1800
const MIN_SPEECH_MS = 200
const WARMUP_MS = 400
const NO_SPEECH_TIMEOUT_MS = 20000
const CALIBRATE_MS = 450

function pickMimeType() {
  const types = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg']
  return types.find((t) => MediaRecorder.isTypeSupported(t)) || ''
}

function cancelAssistantSpeech() {
  if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel()
  }
}

export function useMicRecorder({ onTranscript, onError }) {
  const [recording, setRecording] = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const [supported, setSupported] = useState(false)
  const [level, setLevel] = useState(0)
  const [preview, setPreview] = useState('')

  const streamRef = useRef(null)
  const recorderRef = useRef(null)
  const chunksRef = useRef([])
  const mimeRef = useRef('audio/webm')
  const audioCtxRef = useRef(null)
  const rafRef = useRef(null)
  const maxTimerRef = useRef(null)
  const noSpeechTimerRef = useRef(null)
  const recordStartedAtRef = useRef(0)
  const calibrateUntilRef = useRef(0)
  const noiseFloorRef = useRef(2)
  const speechThresholdRef = useRef(5)
  const lastSoundAtRef = useRef(0)
  const speechAccumMsRef = useRef(0)
  const peakLevelRef = useRef(0)
  const lastTickAtRef = useRef(0)
  const heardSpeechRef = useRef(false)
  const recordingRef = useRef(false)
  const stopRecordingRef = useRef(() => {})
  const onTranscriptRef = useRef(onTranscript)
  const onErrorRef = useRef(onError)

  useEffect(() => {
    onTranscriptRef.current = onTranscript
  }, [onTranscript])

  useEffect(() => {
    onErrorRef.current = onError
  }, [onError])

  useEffect(() => {
    setSupported(
      Boolean(
        typeof window !== 'undefined' &&
          navigator.mediaDevices?.getUserMedia &&
          window.MediaRecorder,
      ),
    )
  }, [])

  const stopMeter = useCallback(() => {
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current)
      rafRef.current = null
    }
    setLevel(0)
    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => {})
      audioCtxRef.current = null
    }
  }, [])

  const releaseStream = useCallback(() => {
    stopMeter()
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
    if (maxTimerRef.current) {
      clearTimeout(maxTimerRef.current)
      maxTimerRef.current = null
    }
    if (noSpeechTimerRef.current) {
      clearTimeout(noSpeechTimerRef.current)
      noSpeechTimerRef.current = null
    }
  }, [stopMeter])

  const startMeter = useCallback((stream) => {
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext
      if (!Ctx) return
      const ctx = new Ctx()
      audioCtxRef.current = ctx
      if (ctx.state === 'suspended') {
        ctx.resume().catch(() => {})
      }
      const source = ctx.createMediaStreamSource(stream)
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 2048
      analyser.smoothingTimeConstant = 0.1
      source.connect(analyser)
      const data = new Uint8Array(analyser.fftSize)
      lastTickAtRef.current = performance.now()

      const tick = () => {
        if (!audioCtxRef.current || !recordingRef.current) return
        analyser.getByteTimeDomainData(data)
        let sum = 0
        for (let i = 0; i < data.length; i += 1) {
          const sample = (data[i] - 128) / 128
          sum += sample * sample
        }
        const rms = Math.sqrt(sum / data.length)
        const pct = Math.min(100, Math.round(rms * 700))
        setLevel(pct)
        if (pct > peakLevelRef.current) peakLevelRef.current = pct

        const now = Date.now()
        const frameMs = Math.min(80, Math.max(8, performance.now() - lastTickAtRef.current))
        lastTickAtRef.current = performance.now()

        if (now < calibrateUntilRef.current) {
          noiseFloorRef.current = Math.max(noiseFloorRef.current, pct)
          speechThresholdRef.current = Math.max(5, Math.round(noiseFloorRef.current * 1.6 + 3))
        }

        const threshold = speechThresholdRef.current
        if (pct > threshold) {
          speechAccumMsRef.current += frameMs
          lastSoundAtRef.current = now
          if (speechAccumMsRef.current >= MIN_SPEECH_MS) {
            heardSpeechRef.current = true
          }
        }

        rafRef.current = requestAnimationFrame(tick)
      }
      tick()
    } catch {
      /* visual meter optional */
    }
  }, [])

  const uploadRecording = useCallback(async () => {
    const chunks = [...chunksRef.current]
    chunksRef.current = []
    const durationMs = Date.now() - recordStartedAtRef.current
    const peak = peakLevelRef.current

    releaseStream()

    if (durationMs < MIN_RECORD_MS) {
      onErrorRef.current?.('too-short')
      return
    }

    const mime = mimeRef.current || 'audio/webm'
    const blob = new Blob(chunks, { type: mime })

    if (!chunks.length || blob.size < MIN_BLOB_BYTES) {
      onErrorRef.current?.(peak > 8 ? 'no-audio' : 'no-speech')
      return
    }

    if (!heardSpeechRef.current && peak < 10) {
      onErrorRef.current?.('too-quiet')
      return
    }

    setTranscribing(true)
    try {
      const { text } = await transcribeJarvisAudio(blob)
      const trimmed = (text || '').trim()
      if (!trimmed) {
        onErrorRef.current?.('no-speech')
        return
      }
      setPreview(trimmed)
      onTranscriptRef.current?.(trimmed)
    } catch (err) {
      onErrorRef.current?.(err.message || 'transcribe_failed')
    } finally {
      setTranscribing(false)
    }
  }, [releaseStream])

  const stopRecording = useCallback(() => {
    if (!recordingRef.current) return
    recordingRef.current = false
    setRecording(false)

    const rec = recorderRef.current
    recorderRef.current = null

    if (!rec) {
      releaseStream()
      onErrorRef.current?.('no-audio')
      return
    }

    const finalize = () => {
      window.setTimeout(() => uploadRecording(), 120)
    }

    if (rec.state === 'recording') {
      try {
        if (typeof rec.requestData === 'function') {
          rec.requestData()
        }
      } catch {
        /* ignore */
      }
      rec.onstop = finalize
      try {
        rec.stop()
      } catch {
        releaseStream()
        onErrorRef.current?.('record_failed')
      }
    } else {
      finalize()
    }
  }, [releaseStream, uploadRecording])

  stopRecordingRef.current = stopRecording

  const startRecording = useCallback(async () => {
    if (recordingRef.current || transcribing) return
    cancelAssistantSpeech()
    setPreview('')
    chunksRef.current = []
    heardSpeechRef.current = false
    speechAccumMsRef.current = 0
    peakLevelRef.current = 0
    noiseFloorRef.current = 2
    speechThresholdRef.current = 5
    lastSoundAtRef.current = 0

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: false,
          autoGainControl: true,
        },
        video: false,
      })

      streamRef.current = stream
      const started = Date.now()
      recordStartedAtRef.current = started
      lastSoundAtRef.current = started
      calibrateUntilRef.current = started + CALIBRATE_MS

      const mime = pickMimeType()
      mimeRef.current = mime || 'audio/webm'

      let recorder
      try {
        recorder = mime
          ? new MediaRecorder(stream, { mimeType: mime, audioBitsPerSecond: 192000 })
          : new MediaRecorder(stream, { audioBitsPerSecond: 192000 })
      } catch {
        recorder = new MediaRecorder(stream)
        mimeRef.current = recorder.mimeType || 'audio/webm'
      }

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          chunksRef.current.push(e.data)
        }
      }

      recorder.onerror = () => {
        recordingRef.current = false
        setRecording(false)
        releaseStream()
        onErrorRef.current?.('record_failed')
      }

      recorder.start(TIMESLICE_MS)
      recorderRef.current = recorder
      recordingRef.current = true
      setRecording(true)

      startMeter(stream)

      maxTimerRef.current = setTimeout(() => {
        stopRecordingRef.current()
      }, MAX_RECORD_MS)

      noSpeechTimerRef.current = setTimeout(() => {
        if (!recordingRef.current || heardSpeechRef.current) return
        stopRecordingRef.current()
      }, NO_SPEECH_TIMEOUT_MS)
    } catch (err) {
      releaseStream()
      recordingRef.current = false
      setRecording(false)
      const name = err?.name || ''
      if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
        onErrorRef.current?.('not-allowed')
      } else if (name === 'NotFoundError') {
        onErrorRef.current?.('audio-capture')
      } else {
        onErrorRef.current?.('record_failed')
      }
    }
  }, [transcribing, releaseStream, startMeter, uploadRecording])

  const startListening = useCallback(() => {
    if (!recordingRef.current && !transcribing) startRecording()
  }, [startRecording, transcribing])

  const stopListening = useCallback(() => {
    if (recordingRef.current) stopRecording()
  }, [stopRecording])

  const clearPreview = useCallback(() => setPreview(''), [])

  useEffect(() => () => releaseStream(), [releaseStream])

  return {
    recording,
    transcribing,
    supported,
    level,
    preview,
    startListening,
    stopListening,
    startRecording,
    clearPreview,
  }
}
