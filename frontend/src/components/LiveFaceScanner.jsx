import { useCallback, useEffect, useRef, useState } from 'react'
import { captureFrameFromVideo } from '../helpers/captureFrame'
import { detectFaceFrame, preloadMediaPipeModels } from '../lib/mediapipeBiometrics'

export default function LiveFaceScanner({
  enabled,
  busy = false,
  onFrame,
  autoStart = false,
  onCameraReadyChange,
  scanIntervalMs = 400,
  captureQuality = 0.88,
  theme = 'light',
}) {
  const dark = theme === 'dark'
  const videoRef = useRef(null)
  const containerRef = useRef(null)
  const streamRef = useRef(null)
  const scanningRef = useRef(false)
  const lastScanRef = useRef(0)
  const eyeEncodingSnapshotRef = useRef(null)

  const [faceBox, setFaceBox] = useState(null)
  const [eyeDots, setEyeDots] = useState([])
  const [captureReady, setCaptureReady] = useState(false)
  const [mpReady, setMpReady] = useState(false)
  const [mpError, setMpError] = useState('')

  const [cameraRequested, setCameraRequested] = useState(autoStart)
  const [cameraReady, setCameraReady] = useState(false)
  const [cameraError, setCameraError] = useState('')

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
    setCameraReady(false)
    setFaceBox(null)
    setEyeDots([])
    setCaptureReady(false)
    eyeEncodingSnapshotRef.current = null
  }, [])

  const startCamera = useCallback(async () => {
    setCameraError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false,
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
        setCameraReady(true)
      }
    } catch {
      setCameraError('Camera access is required. Please allow webcam permissions.')
      setCameraReady(false)
    }
  }, [])

  const openCamera = useCallback(() => {
    setCameraRequested(true)
    setCameraError('')
  }, [])

  useEffect(() => {
    if (autoStart) setCameraRequested(true)
  }, [autoStart])

  useEffect(() => {
    if (!cameraRequested) {
      stopCamera()
      return undefined
    }
    startCamera()
    return () => stopCamera()
  }, [cameraRequested, startCamera, stopCamera])

  useEffect(() => {
    if (!enabled) stopCamera()
  }, [enabled, stopCamera])

  useEffect(() => {
    onCameraReadyChange?.(cameraReady)
  }, [cameraReady, onCameraReadyChange])

  useEffect(() => {
    let cancelled = false
    preloadMediaPipeModels()
      .then(() => {
        if (!cancelled) {
          setMpReady(true)
          setMpError('')
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setMpReady(false)
          setMpError(err?.message || 'Could not load face & eye models. Refresh and try again.')
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  /** Face border + eyes overlay + encode readiness */
  useEffect(() => {
    if (!enabled || busy || !cameraReady || !mpReady) {
      setFaceBox(null)
      setEyeDots([])
      setCaptureReady(false)
      eyeEncodingSnapshotRef.current = null
      return undefined
    }

    let running = true
    const detectingRef = { current: false }

    const tick = async () => {
      if (!running) return
      const video = videoRef.current
      const container = containerRef.current
      if (!video || !container || video.readyState < 2) {
        requestAnimationFrame(tick)
        return
      }

      if (detectingRef.current) {
        requestAnimationFrame(tick)
        return
      }

      detectingRef.current = true
      const ts = performance.now()
      try {
        const result = await detectFaceFrame(video, container, ts)
        if (!running) return

        setFaceBox(result.faceBox)
        setEyeDots(result.eyeDots || [])
        setCaptureReady(Boolean(result.captureReady))
        if (result.captureReady && result.eyeEncoding?.length) {
          eyeEncodingSnapshotRef.current = result.eyeEncoding
        } else {
          eyeEncodingSnapshotRef.current = null
        }
      } finally {
        detectingRef.current = false
        if (running) requestAnimationFrame(tick)
      }
    }

    const id = requestAnimationFrame(tick)
    return () => {
      running = false
      cancelAnimationFrame(id)
      setFaceBox(null)
      setEyeDots([])
      setCaptureReady(false)
      eyeEncodingSnapshotRef.current = null
    }
  }, [enabled, busy, cameraReady, mpReady])

  useEffect(() => {
    const scanAllowed = enabled && !busy && cameraReady && mpReady && captureReady && !mpError

    if (!scanAllowed) return undefined

    const maybeCapture = async () => {
      if (scanningRef.current || busy || !videoRef.current) return
      const now = Date.now()
      if (now - lastScanRef.current < scanIntervalMs) return

      const eyes = eyeEncodingSnapshotRef.current
      if (!eyes?.length) return

      const file = await captureFrameFromVideo(videoRef.current, captureQuality)
      if (!file) return

      lastScanRef.current = now
      scanningRef.current = true
      try {
        await onFrame({ file, eyeEncoding: [...eyes] })
      } finally {
        scanningRef.current = false
      }
    }

    const id = setInterval(maybeCapture, scanIntervalMs)
    maybeCapture()
    return () => clearInterval(id)
  }, [
    enabled,
    busy,
    cameraReady,
    mpReady,
    mpError,
    captureReady,
    onFrame,
    scanIntervalMs,
    captureQuality,
  ])

  const showOpen = !cameraRequested && !cameraError
  const showLoading = cameraRequested && !cameraReady && !cameraError

  let statusLabel = 'Starting camera…'
  let statusColor = 'bg-amber-400 animate-pulse'
  if (cameraReady && mpError) {
    statusLabel = 'Vision models failed'
    statusColor = 'bg-red-400'
  } else if (cameraReady && !mpReady) {
    statusLabel = 'Loading face & eye models…'
    statusColor = 'bg-amber-400 animate-pulse'
  } else if (busy) {
    statusLabel = 'Verifying…'
    statusColor = 'bg-sky-400 animate-pulse'
  } else if (cameraReady && mpReady && !captureReady) {
    statusLabel = 'Show face — both eyes visible'
    statusColor = 'bg-amber-400 animate-pulse'
  } else if (captureReady) {
    statusLabel = 'Scanning…'
    statusColor = 'bg-emerald-400'
  } else if (cameraReady) {
    statusLabel = 'Getting camera…'
    statusColor = 'bg-slate-400 animate-pulse'
  }

  const frameClass = dark
    ? 'overflow-hidden rounded-2xl border border-white/10 bg-[#0b1018] shadow-[0_0_40px_rgba(6,182,212,0.08)]'
    : 'overflow-hidden rounded-2xl border border-slate-200 bg-slate-900 shadow-lg'
  const overlayClass = dark ? 'bg-[#0b1018]' : 'bg-slate-800'
  const openBtnClass = dark
    ? 'cursor-pointer rounded-xl bg-cyan-600 px-6 py-3 text-sm font-semibold text-white hover:bg-cyan-500 disabled:opacity-50'
    : 'cursor-pointer rounded-xl bg-indigo-600 px-6 py-3 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50'
  const iconClass = dark ? 'h-12 w-12 text-cyan-400' : 'h-12 w-12 text-violet-400'
  const retryBtnClass = dark
    ? 'cursor-pointer rounded-xl border border-white/15 bg-[#121a26] px-5 py-2.5 text-sm text-slate-200 hover:bg-white/5'
    : 'cursor-pointer rounded-xl border border-slate-500 bg-slate-700 px-5 py-2.5 text-sm text-white'
  const faceBorderClass = dark
    ? 'pointer-events-none absolute rounded-lg border-2 border-cyan-400 shadow-[0_0_12px_rgba(34,211,238,0.8)]'
    : 'pointer-events-none absolute rounded-lg border-2 border-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.8)]'

  return (
    <div className="w-full">
      <div className={frameClass}>
        <div ref={containerRef} className="relative">
          <video
            ref={videoRef}
            playsInline
            muted
            className={`aspect-[4/3] w-full object-cover ${cameraReady ? 'block' : 'opacity-0'}`}
          />

          {showOpen && (
            <div className={`absolute inset-0 flex aspect-[4/3] flex-col items-center justify-center gap-4 p-6 text-center ${overlayClass}`}>
              <FaceIcon className={iconClass} />
              <p className="max-w-xs text-sm text-slate-300">
                {enabled ? 'Open the camera to scan your face.' : 'Enter your name first.'}
              </p>
              <button
                type="button"
                onClick={openCamera}
                disabled={!enabled}
                className={openBtnClass}
              >
                Open camera
              </button>
            </div>
          )}

          {showLoading && (
            <div className={`absolute inset-0 flex aspect-[4/3] items-center justify-center text-white ${overlayClass}`}>
              <span className="text-sm text-slate-300">Starting camera…</span>
            </div>
          )}

          {cameraError && (
            <div className={`absolute inset-0 flex aspect-[4/3] flex-col items-center justify-center gap-4 p-6 text-center ${overlayClass}`}>
              <p className="text-sm text-red-200">{cameraError}</p>
              <button
                type="button"
                onClick={openCamera}
                className={retryBtnClass}
              >
                Try again
              </button>
            </div>
          )}

          {cameraReady && mpError && (
            <div className="absolute inset-x-0 bottom-16 mx-auto max-w-sm rounded-lg bg-red-950/90 px-3 py-2 text-center text-xs text-red-100">
              {mpError}
            </div>
          )}

          {cameraReady && enabled && (
            <>
              {faceBox && !busy && (
                <div
                  className={faceBorderClass}
                  style={{ left: faceBox.x, top: faceBox.y, width: faceBox.w, height: faceBox.h }}
                />
              )}
              {eyeDots.map((dot) => (
                <div
                  key={dot.side}
                  className="pointer-events-none absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-cyan-400 shadow-[0_0_10px_rgba(34,211,238,0.95)]"
                  style={{ left: dot.x, top: dot.y }}
                  aria-hidden
                />
              ))}
              <div className="absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-2 rounded-full bg-black/60 px-3 py-1.5 text-xs font-medium text-white">
                <span className={`h-2 w-2 rounded-full ${statusColor}`} />
                {statusLabel}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function FaceIcon({ className }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0"
      />
    </svg>
  )
}
