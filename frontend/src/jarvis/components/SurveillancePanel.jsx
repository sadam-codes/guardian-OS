import { useCallback, useEffect, useRef, useState } from 'react'
import { preloadMediaPipeModels } from '../../lib/mediapipeBiometrics'
import { GESTURE_LABELS } from '../../lib/gestureRecognition'
import { useGestureControl } from '../hooks/useGestureControl'
import { useGuardianSurveillance } from '../hooks/useGuardianSurveillance'

export default function SurveillancePanel({ session, onIdentityChange, onGestureCommand }) {
  const videoRef = useRef(null)
  const containerRef = useRef(null)
  const streamRef = useRef(null)
  const [cameraReady, setCameraReady] = useState(false)
  const [cameraError, setCameraError] = useState('')
  const [surveillanceOn, setSurveillanceOn] = useState(true)

  const {
    identityVerified,
    activeUser,
    facePresent,
    surveillanceLog,
    verifyIdentity,
    reportEvent,
  } = useGuardianSurveillance({
    session,
    enabled: surveillanceOn && cameraReady,
    videoRef,
    containerRef,
  })

  const onGesture = useCallback(
    (gesture) => {
      reportEvent('gesture_action', gesture)
      onGestureCommand?.(gesture)
    },
    [reportEvent, onGestureCommand],
  )

  const { lastGesture } = useGestureControl({
    enabled: surveillanceOn && cameraReady,
    videoRef,
    onGesture,
  })

  useEffect(() => {
    onIdentityChange?.({ identityVerified, activeUser, facePresent })
  }, [identityVerified, activeUser, facePresent, onIdentityChange])

  useEffect(() => {
    let cancelled = false
    preloadMediaPipeModels().catch(() => {})

    async function start() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
          audio: false,
        })
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop())
          return
        }
        streamRef.current = stream
        if (videoRef.current) {
          videoRef.current.srcObject = stream
          await videoRef.current.play()
          setCameraReady(true)
          setCameraError('')
        }
      } catch {
        setCameraError('Allow camera access for Guardian surveillance.')
        setCameraReady(false)
      }
    }

    start()
    return () => {
      cancelled = true
      streamRef.current?.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
  }, [])

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">Live surveillance</h2>
          <p className="text-xs text-slate-500">Face · eyes · gestures · security</p>
        </div>
        <label className="flex cursor-pointer items-center gap-2 text-xs text-slate-600">
          <input
            type="checkbox"
            checked={surveillanceOn}
            onChange={(e) => setSurveillanceOn(e.target.checked)}
            className="rounded border-slate-300"
          />
          Active
        </label>
      </div>

      <div className="grid gap-4 p-4 lg:grid-cols-[1fr_200px]">
        <div
          ref={containerRef}
          className="relative aspect-video overflow-hidden rounded-lg bg-slate-900"
        >
          <video
            ref={videoRef}
            playsInline
            muted
            className="h-full w-full scale-x-[-1] object-cover"
          />
          {!cameraReady && (
            <p className="absolute inset-0 flex items-center justify-center text-sm text-slate-300">
              {cameraError || 'Starting camera…'}
            </p>
          )}
          <div className="absolute left-2 top-2 flex flex-wrap gap-1">
            <StatusPill
              label={identityVerified ? 'Verified' : 'Unverified'}
              ok={identityVerified}
            />
            <StatusPill label={facePresent ? 'Face' : 'No face'} ok={facePresent} />
          </div>
          </div>

        <div className="space-y-3 text-xs">
          <div>
            <p className="font-semibold text-slate-700">Active user</p>
            <p className="text-slate-900">{activeUser || session?.name || '—'}</p>
          </div>
          <button
            type="button"
            onClick={verifyIdentity}
            className="w-full cursor-pointer rounded-lg border border-indigo-200 bg-indigo-50 py-1.5 text-xs font-medium text-indigo-800 hover:bg-indigo-100"
          >
            Re-verify face now
          </button>
          {lastGesture && (
            <p className="rounded-md bg-violet-50 px-2 py-1 text-violet-900">
              Gesture: {GESTURE_LABELS[lastGesture] || lastGesture}
            </p>
          )}
          <div>
            <p className="mb-1 font-semibold text-slate-700">Security log</p>
            <ul className="max-h-32 space-y-1 overflow-y-auto">
              {surveillanceLog.length === 0 && (
                <li className="text-slate-400">No events yet</li>
              )}
              {surveillanceLog.map((e) => (
                <li key={e.id} className="rounded border border-slate-100 bg-slate-50 px-2 py-1">
                  <span className="font-medium">{e.type}</span>: {e.message}
                </li>
              ))}
            </ul>
          </div>
          <p className="text-[10px] text-slate-400">
            Fingerprint: mock slot (enrollment UI only). Unknown face → auto-lock when enabled.
          </p>
        </div>
      </div>
    </div>  
  )
}

function StatusPill({ label, ok }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
        ok ? 'bg-emerald-500/90 text-white' : 'bg-amber-500/90 text-white'
      }`}
    >
      {label}
    </span>
  )
}
