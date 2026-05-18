/** Browser TTS fallback when Vapi/ElevenLabs stream is silent. */

function pickFemaleEnglishVoice() {
  if (!('speechSynthesis' in window)) return null
  const voices = window.speechSynthesis.getVoices()
  if (!voices.length) return null
  const isEnglish = (v) => v.lang.toLowerCase().startsWith('en')
  const label = (v) => `${v.name} ${v.voiceURI}`.toLowerCase()
  const isMale = (v) =>
    /male|david|guy|daniel|mark|ryan|james|george|brian|eric|steven|richard|andrew/i.test(
      label(v),
    )
  const isFemale = (v) =>
    isEnglish(v) &&
    !isMale(v) &&
    /female|zira|jenny|samantha|susan|linda|karen|aria|emma|hazel|natasha|laura|joanna|kimberly|salli|sonia|veena|michelle|helen|lily/i.test(
      label(v),
    )
  return (
    voices.find(isFemale) ||
    voices.find((v) => isEnglish(v) && !isMale(v)) ||
    voices.find(isEnglish) ||
    voices[0]
  )
}

export function speakBrowser(text) {
  if (!('speechSynthesis' in window) || !text?.trim()) return
  window.speechSynthesis.cancel()
  const utter = new SpeechSynthesisUtterance(text.trim())
  const voice = pickFemaleEnglishVoice()
  if (voice) utter.voice = voice
  utter.rate = 0.96
  utter.pitch = 1.05
  window.speechSynthesis.speak(utter)
}

const API_BASE = import.meta.env.VITE_API_URL || '/api'

/** ElevenLabs via backend — works when Vapi integration 401. */
export async function speakElevenLabs(text) {
  const res = await fetch(`${API_BASE}/vapi/speak`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: text.trim() }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Speak failed (${res.status})`)
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const audio = new Audio(url)
  await audio.play()
  audio.onended = () => URL.revokeObjectURL(url)
}

export async function speakWithFallback(text) {
  try {
    await speakElevenLabs(text)
    return { mode: 'elevenlabs', error: null }
  } catch (err) {
    const msg = err?.message || String(err)
    const keyInvalid = /401|invalid|unauthorized/i.test(msg)
    if (!keyInvalid) {
      speakBrowser(text)
      return { mode: 'browser', error: msg }
    }
    return { mode: 'none', error: msg }
  }
}
