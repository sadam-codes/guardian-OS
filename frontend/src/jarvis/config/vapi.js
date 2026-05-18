/** Vapi voice — used instead of browser mic + speechSynthesis when configured. */

export const VAPI_PUBLIC_KEY = import.meta.env.VITE_VAPI_PUBLIC_KEY || ''
export const VAPI_ASSISTANT_ID = import.meta.env.VITE_VAPI_ASSISTANT_ID || ''

export function isVapiConfigured() {
  return Boolean(VAPI_PUBLIC_KEY.trim() && VAPI_ASSISTANT_ID.trim())
}
