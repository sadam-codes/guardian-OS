import { useCallback, useEffect, useRef, useState } from 'react'
import { captureFrameFromVideo } from '../helpers/captureFrame'

const SCAN_MS = 1800

export default function LiveFaceScanner({
  enabled,
  paused,
  onFrame,
  status = 'scanning',
  hint = 'Position your face in the frame',
  autoStart = false,
  onCameraReadyChange,
}) {
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const scanningRef = useRef(false)
  const [cameraRequested, setCameraRequested] = useState(autoStart)
  const [cameraReady, setCameraReady] = useState(false)
  const [cameraError, setCameraError] = useState('')

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
    setCameraReady(false)
  }, [])

  const startCamera = useCallback(async () => {
    setCameraError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
        setCameraReady(true)
      }
    } catch {
      setCameraError('Camera access is required. Please allow webcam permissions in your browser.')
      setCameraReady(false)
    }
  }, [])

  const openCamera = useCallback(() => {
    setCameraRequested(true)
    setCameraError('')
  }, [])

  useEffect(() => {
    if (autoStart) {
      setCameraRequested(true)
    }
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
    if (!enabled) {
      stopCamera()
      if (!autoStart) {
        setCameraRequested(false)
      }
    }
  }, [enabled, autoStart, stopCamera])

  useEffect(() => {
    onCameraReadyChange?.(cameraReady)
  }, [cameraReady, onCameraReadyChange])

  useEffect(() => {
    if (!enabled || paused || !cameraReady) return

    const tick = async () => {
      if (scanningRef.current || paused || !videoRef.current) return
      const file = await captureFrameFromVideo(videoRef.current)
      if (!file) return

      scanningRef.current = true
      try {
        await onFrame(file)
      } finally {
        scanningRef.current = false
      }
    }

    const id = setInterval(tick, SCAN_MS)
    tick()
    return () => clearInterval(id)
  }, [enabled, paused, cameraReady, onFrame])

  const ringClass =
    status === 'recognized'
      ? 'border-emerald-500 shadow-[0_0_0_4px_rgba(16,185,129,0.25)]'
      : status === 'error'
        ? 'border-red-400'
        : 'border-indigo-500/80 shadow-[0_0_0_4px_rgba(99,102,241,0.15)]'

  const showOpenButton = !cameraRequested && !cameraError
  const showLoading = cameraRequested && !cameraReady && !cameraError

  return (
    <div className="w-full">
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-slate-900 shadow-lg">
        <div className="relative">
          <video
            ref={videoRef}
            playsInline
            muted
            className={`aspect-[4/3] w-full object-cover ${cameraReady ? 'block' : 'opacity-0'}`}
          />

          {showOpenButton && (
            <div className="absolute inset-0 flex aspect-[4/3] flex-col items-center justify-center gap-4 bg-slate-800 p-6 text-center">
              <CameraIcon className="h-12 w-12 text-slate-400" />
              <p className="max-w-xs text-sm text-slate-300">
                {enabled
                  ? 'Open the camera when you are ready to scan your face.'
                  : 'Complete the form above, then open the camera.'}
              </p>
              <button
                type="button"
                onClick={openCamera}
                disabled={!enabled}
                className="cursor-pointer rounded-xl bg-indigo-600 px-6 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Open camera
              </button>
            </div>
          )}

          {showLoading && (
            <div className="absolute inset-0 flex aspect-[4/3] flex-col items-center justify-center gap-3 bg-slate-800 text-white">
              <Spinner />
              <span className="text-sm text-slate-300">Starting camera…</span>
            </div>
          )}

          {cameraError && (
            <div className="absolute inset-0 flex aspect-[4/3] flex-col items-center justify-center gap-4 bg-slate-800 p-6 text-center">
              <p className="text-sm text-red-200">{cameraError}</p>
              <button
                type="button"
                onClick={openCamera}
                className="rounded-xl border border-slate-500 bg-slate-700 px-5 py-2.5 text-sm font-medium text-white hover:bg-slate-600"
              >
                Try again
              </button>
            </div>
          )}

          {cameraReady && (
            <>
              <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-slate-900/50 via-transparent to-slate-900/20" />
              <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                <div
                  className={`h-52 w-52 rounded-full border-[3px] ${ringClass} transition-all duration-500`}
                />
              </div>
              {enabled && !paused && status === 'scanning' && (
                <div className="absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-2 rounded-full bg-black/50 px-3 py-1.5 text-xs text-white backdrop-blur-sm">
                  <span className="h-2 w-2 animate-pulse rounded-full bg-indigo-400" />
                  Scanning…
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <p className="mt-3 text-center text-sm text-slate-500">{hint}</p>
    </div>
  )
}

function CameraIcon({ className }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a41.763 41.763 0 00-1.134-.175 2.31 2.31 0 00-1.64-1.055 2.31 2.31 0 00-1.64 1.055 41.763 41.763 0 00-1.134.175C4.749 7.58 4 8.507 4 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169z"
      />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  )
}

function Spinner() {
  return (
    <svg className="h-8 w-8 animate-spin text-indigo-400" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  )
}
