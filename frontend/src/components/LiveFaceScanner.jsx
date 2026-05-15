import { useCallback, useEffect, useRef, useState } from 'react'
import { captureFrameFromVideo } from '../helpers/captureFrame'

const FACE_DETECT_MS = 120

export default function LiveFaceScanner({
  enabled,
  busy = false,
  onFrame,
  autoStart = false,
  onCameraReadyChange,
  scanIntervalMs = 400,
  captureQuality = 0.88,
}) {
  const videoRef = useRef(null)
  const containerRef = useRef(null)
  const streamRef = useRef(null)
  const scanningRef = useRef(false)
  const lastScanRef = useRef(0)
  const faceDetectorRef = useRef(null)
  const [faceBox, setFaceBox] = useState(null)
  const [ready, setReady] = useState(false)
  const [cameraRequested, setCameraRequested] = useState(autoStart)
  const [cameraReady, setCameraReady] = useState(false)
  const [cameraError, setCameraError] = useState('')
  const [useNativeDetector, setUseNativeDetector] = useState(false)

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
    setCameraReady(false)
    setReady(false)
    setFaceBox(null)
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
    if (typeof window === 'undefined' || !('FaceDetector' in window)) return undefined
    let cancelled = false
    try {
      faceDetectorRef.current = new window.FaceDetector({ fastMode: true, maxDetectedFaces: 1 })
      if (!cancelled) setUseNativeDetector(true)
    } catch {
      setUseNativeDetector(false)
    }
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!enabled || busy || !cameraReady) {
      setReady(false)
      setFaceBox(null)
      return undefined
    }

    let running = true
    let lastDetect = 0

    const detectLoop = (now) => {
      if (!running) return
      const video = videoRef.current
      const container = containerRef.current
      if (!video || !container || video.readyState < 2) {
        requestAnimationFrame(detectLoop)
        return
      }

      if (now - lastDetect >= FACE_DETECT_MS) {
        lastDetect = now

        if (useNativeDetector && faceDetectorRef.current) {
          faceDetectorRef.current
            .detect(video)
            .then((faces) => {
              if (!running) return
              if (faces?.length) {
                setReady(true)
                const b = faces[0].boundingBox
                const scaleX = container.clientWidth / video.videoWidth
                const scaleY = container.clientHeight / video.videoHeight
                setFaceBox({
                  x: b.x * scaleX,
                  y: b.y * scaleY,
                  w: b.width * scaleX,
                  h: b.height * scaleY,
                })
              } else {
                setReady(false)
                setFaceBox(null)
              }
            })
            .catch(() => {
              if (running) setReady(true)
            })
        } else {
          setReady(true)
        }
      }

      requestAnimationFrame(detectLoop)
    }

    const id = requestAnimationFrame(detectLoop)
    return () => {
      running = false
      cancelAnimationFrame(id)
      setReady(false)
      setFaceBox(null)
    }
  }, [enabled, busy, cameraReady, useNativeDetector])

  useEffect(() => {
    if (!enabled || busy || !cameraReady || !ready) return undefined

    const tick = async () => {
      if (scanningRef.current || busy || !videoRef.current) return
      const now = Date.now()
      if (now - lastScanRef.current < scanIntervalMs) return

      const file = await captureFrameFromVideo(videoRef.current, captureQuality)
      if (!file) return

      lastScanRef.current = now
      scanningRef.current = true
      try {
        await onFrame(file)
      } finally {
        scanningRef.current = false
      }
    }

    const id = setInterval(tick, scanIntervalMs)
    tick()
    return () => clearInterval(id)
  }, [enabled, busy, cameraReady, ready, onFrame, scanIntervalMs, captureQuality])

  const showOpen = !cameraRequested && !cameraError
  const showLoading = cameraRequested && !cameraReady && !cameraError

  let statusLabel = 'Looking for face…'
  let statusColor = 'bg-amber-400 animate-pulse'
  if (busy) {
    statusLabel = 'Verifying…'
    statusColor = 'bg-sky-400 animate-pulse'
  } else if (ready) {
    statusLabel = 'Scanning…'
    statusColor = 'bg-emerald-400'
  }

  return (
    <div className="w-full">
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-slate-900 shadow-lg">
        <div ref={containerRef} className="relative">
          <video
            ref={videoRef}
            playsInline
            muted
            className={`aspect-[4/3] w-full object-cover ${cameraReady ? 'block' : 'opacity-0'}`}
          />

          {showOpen && (
            <div className="absolute inset-0 flex aspect-[4/3] flex-col items-center justify-center gap-4 bg-slate-800 p-6 text-center">
              <FaceIcon className="h-12 w-12 text-violet-400" />
              <p className="max-w-xs text-sm text-slate-300">
                {enabled ? 'Open the camera to scan your face.' : 'Enter your name first.'}
              </p>
              <button
                type="button"
                onClick={openCamera}
                disabled={!enabled}
                className="cursor-pointer rounded-xl bg-indigo-600 px-6 py-3 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
              >
                Open camera
              </button>
            </div>
          )}

          {showLoading && (
            <div className="absolute inset-0 flex aspect-[4/3] items-center justify-center bg-slate-800 text-white">
              <span className="text-sm text-slate-300">Starting camera…</span>
            </div>
          )}

          {cameraError && (
            <div className="absolute inset-0 flex aspect-[4/3] flex-col items-center justify-center gap-4 bg-slate-800 p-6 text-center">
              <p className="text-sm text-red-200">{cameraError}</p>
              <button
                type="button"
                onClick={openCamera}
                className="cursor-pointer rounded-xl border border-slate-500 bg-slate-700 px-5 py-2.5 text-sm text-white"
              >
                Try again
              </button>
            </div>
          )}

          {cameraReady && enabled && (
            <>
              {faceBox && !busy && (
                <div
                  className="pointer-events-none absolute rounded-lg border-2 border-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.8)]"
                  style={{ left: faceBox.x, top: faceBox.y, width: faceBox.w, height: faceBox.h }}
                />
              )}
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
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0" />
    </svg>
  )
}

