import { FaceLandmarker, FilesetResolver, HandLandmarker } from '@mediapipe/tasks-vision'

const WASM_CDN = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision/wasm'
const FACE_MODEL =
  'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task'
const HAND_MODEL =
  'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task'

export const BIOMETRIC_EYE = 'eye'
export const BIOMETRIC_FACE = 'face'
export const BIOMETRIC_PALM = 'palm'

const LEFT_EYE = [33, 160, 158, 133, 153, 144, 145]
const RIGHT_EYE = [362, 385, 387, 263, 373, 380, 381]
const FACE_ENCODE = [
  10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148,
  176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109, 33, 133, 362, 263, 1, 199,
  61, 291, 13, 14, 78, 308,
]
const FACE_DIST_PAIRS = [
  [33, 263],
  [61, 291],
  [13, 14],
  [78, 308],
  [10, 152],
  [234, 454],
]
const EYE_V48_PAIRS = [
  [33, 133],
  [160, 144],
  [158, 153],
  [362, 263],
  [385, 380],
  [387, 373],
]
const PALM_BASES = [0, 1, 5, 9, 13, 17]

let faceLandmarker = null
let handLandmarker = null
let loadPromise = null

async function createWithDelegate(ModelClass, vision, modelPath, options) {
  try {
    return await ModelClass.createFromOptions(vision, {
      ...options,
      baseOptions: { modelAssetPath: modelPath, delegate: 'GPU' },
    })
  } catch {
    return ModelClass.createFromOptions(vision, {
      ...options,
      baseOptions: { modelAssetPath: modelPath, delegate: 'CPU' },
    })
  }
}

export async function ensureModels() {
  if (faceLandmarker && handLandmarker) {
    return { faceLandmarker, handLandmarker }
  }

  if (!loadPromise) {
    loadPromise = (async () => {
      const vision = await FilesetResolver.forVisionTasks(WASM_CDN)
      const [face, hand] = await Promise.all([
        createWithDelegate(FaceLandmarker, vision, FACE_MODEL, {
          runningMode: 'VIDEO',
          numFaces: 1,
          outputFaceBlendshapes: false,
        }),
        createWithDelegate(HandLandmarker, vision, HAND_MODEL, {
          runningMode: 'VIDEO',
          numHands: 1,
        }),
      ])
      faceLandmarker = face
      handLandmarker = hand
      return { faceLandmarker, handLandmarker }
    })()
  }

  return loadPromise
}

export function preloadMediaPipeModels() {
  return ensureModels()
}

export function normalizeVector(values) {
  const norm = Math.sqrt(values.reduce((s, v) => s + v * v, 0)) || 1
  return values.map((v) => v / norm)
}

function pairwiseDistances(points, pairs) {
  const out = []
  for (const [a, b] of pairs) {
    const pa = points[a]
    const pb = points[b]
    if (!pa || !pb) continue
    out.push(Math.hypot(pa.x - pb.x, pa.y - pb.y, (pa.z || 0) - (pb.z || 0)))
  }
  return out
}

function faceScaleAndCenter(landmarks) {
  const nose = landmarks[1]
  const left = landmarks[33]
  const right = landmarks[362]
  let scale = Math.hypot(right.x - left.x, right.y - left.y)
  if (scale < 1e-6) scale = 1
  return { cx: nose.x, cy: nose.y, cz: nose.z || 0, scale }
}

function toRelativePoints(landmarks, cx, cy, cz, scale) {
  return landmarks.map((p) => ({
    x: (p.x - cx) / scale,
    y: (p.y - cy) / scale,
    z: ((p.z || 0) - cz) / scale,
  }))
}

function encodeEyeIdentity(landmarks) {
  let minX = Infinity
  let maxX = -Infinity
  let minY = Infinity
  let maxY = -Infinity
  for (const p of landmarks) {
    minX = Math.min(minX, p.x)
    maxX = Math.max(maxX, p.x)
    minY = Math.min(minY, p.y)
    maxY = Math.max(maxY, p.y)
  }
  const fw = Math.max(maxX - minX, 1e-6)
  const fh = Math.max(maxY - minY, 1e-6)
  const cx = (minX + maxX) / 2
  const cy = (minY + maxY) / 2

  const rel = landmarks.map((p) => ({
    x: (p.x - cx) / fw,
    y: (p.y - cy) / fh,
    z: (p.z || 0) / fw,
  }))

  const eyeIndices = [...LEFT_EYE, ...RIGHT_EYE]
  const out = []
  for (const i of eyeIndices) {
    const p = rel[i]
    out.push(p.x, p.y, p.z)
  }
  out.push(...pairwiseDistances(rel, EYE_V48_PAIRS))
  return normalizeVector(out)
}

function encodeFaceLandmarks(landmarks, indices, extraPairs = []) {
  const { cx, cy, cz, scale } = faceScaleAndCenter(landmarks)
  const rel = toRelativePoints(landmarks, cx, cy, cz, scale)
  const out = []
  for (const i of indices) {
    const p = rel[i]
    out.push(p.x, p.y, p.z)
  }
  out.push(...pairwiseDistances(rel, extraPairs))
  return normalizeVector(out)
}

function encodeHandLandmarks(landmarks) {
  const wrist = landmarks[0]
  const mid = landmarks[9]
  let scale = Math.hypot(mid.x - wrist.x, mid.y - wrist.y)
  if (scale < 1e-6) scale = 1
  const rel = toRelativePoints(landmarks, wrist.x, wrist.y, wrist.z || 0, scale)

  const out = []
  for (const p of rel) out.push(p.x, p.y, p.z)

  const tips = [4, 8, 12, 16, 20].map((i) => rel[i])
  for (let a = 0; a < tips.length; a += 1) {
    for (let b = a + 1; b < tips.length; b += 1) {
      out.push(Math.hypot(tips[a].x - tips[b].x, tips[a].y - tips[b].y, tips[a].z - tips[b].z))
    }
  }
  return normalizeVector(out)
}

export function buildEncoding(biometricType, landmarks) {
  if (biometricType === BIOMETRIC_PALM) {
    return encodeHandLandmarks(landmarks)
  }
  if (biometricType === BIOMETRIC_FACE) {
    return encodeFaceLandmarks(landmarks, FACE_ENCODE, FACE_DIST_PAIRS)
  }
  return encodeEyeIdentity(landmarks)
}

export function averageEncodings(samples) {
  if (!samples.length) return null
  const dim = samples[0].length
  const out = new Array(dim).fill(0)
  for (const sample of samples) {
    for (let i = 0; i < dim; i += 1) out[i] += sample[i]
  }
  for (let i = 0; i < dim; i += 1) out[i] /= samples.length
  return normalizeVector(out)
}

export function mapNormToDisplay(norm, video, container) {
  const vw = video.videoWidth
  const vh = video.videoHeight
  const cw = container.clientWidth
  const ch = container.clientHeight
  if (!vw || !vh || !cw || !ch) return null

  const px = norm.x * vw
  const py = norm.y * vh
  const videoAspect = vw / vh
  const boxAspect = cw / ch

  let scale
  let offsetX
  let offsetY
  if (videoAspect > boxAspect) {
    scale = ch / vh
    offsetX = (cw - vw * scale) / 2
    offsetY = 0
  } else {
    scale = cw / vw
    offsetX = 0
    offsetY = (ch - vh * scale) / 2
  }

  return { x: px * scale + offsetX, y: py * scale + offsetY }
}

export function eyeCenter(landmarks, indices) {
  let x = 0
  let y = 0
  for (const i of indices) {
    x += landmarks[i].x
    y += landmarks[i].y
  }
  const n = indices.length
  return { x: x / n, y: y / n }
}

/** Face bbox + eye dots + encoding for Guardian scanner (single FaceLandmarker pass). */
export async function detectFaceFrame(video, container, timestamp) {
  const empty = {
    captureReady: false,
    faceBox: null,
    eyeDots: [],
    eyeEncoding: null,
    modelReady: false,
  }

  if (!video?.videoWidth || !container) {
    return empty
  }

  try {
    const { faceLandmarker: faceLm } = await ensureModels()
    const result = faceLm.detectForVideo(video, timestamp)
    const face = result.faceLandmarks?.[0]
    if (!face) {
      return { ...empty, modelReady: true }
    }

    const faceBox = landmarkBoundingBoxDisplay(face, video, container)
    const left = eyeCenter(face, LEFT_EYE)
    const right = eyeCenter(face, RIGHT_EYE)
    const leftPx = mapNormToDisplay(left, video, container)
    const rightPx = mapNormToDisplay(right, video, container)

    const eyeDots = []
    if (leftPx) eyeDots.push({ ...leftPx, side: 'left' })
    if (rightPx) eyeDots.push({ ...rightPx, side: 'right' })

    const eyesOk = Boolean(leftPx && rightPx && faceBox)
    const eyeEncoding = eyesOk ? buildEncoding(BIOMETRIC_EYE, face) : null

    return {
      captureReady: Boolean(eyesOk),
      faceBox,
      eyeDots,
      eyeEncoding,
      modelReady: true,
    }
  } catch {
    return { ...empty, modelReady: false }
  }
}

function landmarkBoundingBoxDisplay(face, video, container) {
  let minX = 1
  let maxX = 0
  let minY = 1
  let maxY = 0
  for (const p of face) {
    minX = Math.min(minX, p.x)
    maxX = Math.max(maxX, p.x)
    minY = Math.min(minY, p.y)
    maxY = Math.max(maxY, p.y)
  }
  const bw = maxX - minX
  const bh = maxY - minY
  const pad = Math.max(bw, bh, 1e-6) * 0.08
  minX = Math.max(0, minX - pad)
  maxX = Math.min(1, maxX + pad)
  minY = Math.max(0, minY - pad)
  maxY = Math.min(1, maxY + pad)

  const tl = mapNormToDisplay({ x: minX, y: minY }, video, container)
  const br = mapNormToDisplay({ x: maxX, y: maxY }, video, container)
  if (!tl || !br) return null

  const x = Math.min(tl.x, br.x)
  const y = Math.min(tl.y, br.y)
  const w = Math.abs(br.x - tl.x)
  const h = Math.abs(br.y - tl.y)
  if (w < 8 || h < 8) return null
  return { x, y, w, h }
}

export async function detectBiometric(video, container, biometricType, timestamp) {
  if (!video?.videoWidth) {
    return { detected: false, encoding: null, overlay: [] }
  }

  const { faceLandmarker: faceLm, handLandmarker: handLm } = await ensureModels()

  if (biometricType === BIOMETRIC_PALM) {
    const result = handLm.detectForVideo(video, timestamp)
    const hand = result.landmarks?.[0]
    if (!hand) return { detected: false, encoding: null, overlay: [] }

    const center = palmCenter(hand)
    const px = mapNormToDisplay(center, video, container)
    const overlay = px ? [{ ...px, kind: 'palm' }] : []
    return {
      detected: true,
      encoding: buildEncoding(BIOMETRIC_PALM, hand),
      overlay,
    }
  }

  const result = faceLm.detectForVideo(video, timestamp)
  const face = result.faceLandmarks?.[0]
  if (!face) return { detected: false, encoding: null, overlay: [] }

  if (biometricType === BIOMETRIC_FACE) {
    const nose = mapNormToDisplay(face[1], video, container)
    const overlay = nose ? [{ ...nose, kind: 'face', id: 0 }] : []
    return {
      detected: true,
      encoding: buildEncoding(BIOMETRIC_FACE, face),
      overlay,
    }
  }

  const left = eyeCenter(face, LEFT_EYE)
  const right = eyeCenter(face, RIGHT_EYE)
  const leftPx = mapNormToDisplay(left, video, container)
  const rightPx = mapNormToDisplay(right, video, container)
  const overlay = []
  if (leftPx) overlay.push({ ...leftPx, kind: 'eye', side: 'left' })
  if (rightPx) overlay.push({ ...rightPx, kind: 'eye', side: 'right' })

  return {
    detected: Boolean(leftPx && rightPx),
    encoding: buildEncoding(BIOMETRIC_EYE, face),
    overlay,
  }
}

function palmCenter(landmarks) {
  let x = 0
  let y = 0
  for (const i of PALM_BASES) {
    x += landmarks[i].x
    y += landmarks[i].y
  }
  const n = PALM_BASES.length
  return { x: x / n, y: y / n }
}

preloadMediaPipeModels().catch(() => {})
