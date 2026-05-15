import { useEffect, useRef, useState } from 'react'
import { BIOMETRIC_EYE, BIOMETRIC_FACE, detectBiometric, preloadMediaPipeModels } from '../lib/mediapipeBiometrics'

export function preloadFaceLandmarker() {
  return preloadMediaPipeModels()
}

export function preloadHandLandmarker() {
  return preloadMediaPipeModels()
}

export function useMediaPipeBiometric(videoRef, containerRef, biometricType, active) {
  const [overlay, setOverlay] = useState([])
  const [detected, setDetected] = useState(false)
  const [modelReady, setModelReady] = useState(false)
  const [modelError, setModelError] = useState('')
  const encodingRef = useRef(null)
  const detectedRef = useRef(false)
  const rafRef = useRef(0)
  const tsRef = useRef(0)
  const inFlightRef = useRef(false)
  const frameSkipRef = useRef(0)

  useEffect(() => {
    let cancelled = false
    setModelError('')
    preloadMediaPipeModels()
      .then(() => {
        if (!cancelled) {
          setModelReady(true)
          setModelError('')
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setModelReady(false)
          setModelError(err?.message || 'Could not load detection models. Check internet and refresh.')
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!active || !modelReady) {
      setOverlay([])
      setDetected(false)
      detectedRef.current = false
      encodingRef.current = null
      return undefined
    }

    let running = true

    const scheduleNext = () => {
      if (running) rafRef.current = requestAnimationFrame(tick)
    }

    const tick = () => {
      if (!running) return

      const video = videoRef.current
      const container = containerRef.current
      if (!video || !container || video.readyState < 2) {
        scheduleNext()
        return
      }

      if (inFlightRef.current) {
        scheduleNext()
        return
      }

      frameSkipRef.current += 1
      tsRef.current = performance.now()
      inFlightRef.current = true

      detectBiometric(video, container, biometricType, tsRef.current)
        .then((result) => {
          if (!running) return

          encodingRef.current = result.detected ? result.encoding : null
          detectedRef.current = result.detected

          setDetected(result.detected)
          if (frameSkipRef.current % 2 === 0) {
            setOverlay(result.overlay)
          }
        })
        .catch((err) => {
          if (!running) return
          encodingRef.current = null
          detectedRef.current = false
          setOverlay([])
          setDetected(false)
          setModelError(err?.message || 'Detection failed')
        })
        .finally(() => {
          inFlightRef.current = false
          if (running) scheduleNext()
        })
    }

    rafRef.current = requestAnimationFrame(tick)
    return () => {
      running = false
      cancelAnimationFrame(rafRef.current)
      inFlightRef.current = false
      setOverlay([])
      setDetected(false)
      detectedRef.current = false
      encodingRef.current = null
    }
  }, [active, modelReady, biometricType, videoRef, containerRef])

  const eyes = overlay.filter((p) => p.kind === 'eye')
  const palm = overlay.find((p) => p.kind === 'palm') || null
  const facePoints = overlay.filter((p) => p.kind === 'face')

  return {
    overlay,
    detected,
    modelReady,
    modelError,
    getEncoding: () => encodingRef.current,
    isDetected: () => detectedRef.current,
    eyes,
    palm,
    facePoints,
    bothEyesVisible: biometricType === BIOMETRIC_EYE && detected,
    palmVisible: biometricType === 'palm' && detected,
    faceVisible: biometricType === BIOMETRIC_FACE && detected,
  }
}

export function useEyeLandmarks(videoRef, containerRef, active) {
  return useMediaPipeBiometric(videoRef, containerRef, BIOMETRIC_EYE, active)
}

export function usePalmLandmarks(videoRef, containerRef, active) {
  return useMediaPipeBiometric(videoRef, containerRef, 'palm', active)
}
