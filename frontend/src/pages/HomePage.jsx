import { useCallback, useEffect, useRef, useState } from 'react'
import { faceLogin, faceSignup } from '../api/face'
import EyeAuthIllustration from '../components/EyeAuthIllustration'
import LiveFaceScanner from '../components/LiveFaceScanner'
import PageHeader from '../components/PageHeader'
import ScanStatusBanner from '../components/ScanStatusBanner'
import { useToast } from '../components/ToastProvider'
import {
  faceCreatingAccountMessage,
  faceIdleMessage,
  faceProgressMessage,
  faceSuccessMessage,
  faceVerifyingMessage,
  parseFaceAuthError,
} from '../helpers/faceMessages'
import { clearSession, redirectForRole, setSession } from '../lib/session'

const MODES = { signup: 'signup', login: 'login' }
const ROLE_ADMIN = 'admin'
const SIGNUP_SAMPLE_COUNT = 3
const LOGIN_SAMPLE_COUNT = 3

const AUTH_TAGS = ['Face match', 'Iris encode', 'Secure session']

export default function HomePage() {
  const [mode, setMode] = useState(MODES.login)
  const [name, setName] = useState('')
  const [scanMessage, setScanMessage] = useState(() => faceIdleMessage(MODES.login))
  const [isProcessing, setIsProcessing] = useState(false)
  const signupDoneRef = useRef(false)
  const loginBusyRef = useRef(false)
  const loginAttemptRef = useRef(0)
  const signupSamplesRef = useRef([])
  const signupEyeSamplesRef = useRef([])
  const loginSamplesRef = useRef([])
  const loginEyeSamplesRef = useRef([])
  const [signupBlocked, setSignupBlocked] = useState(false)
  const toast = useToast()

  useEffect(() => {
    clearSession()
  }, [])

  const resetScan = useCallback((nextMode) => {
    loginAttemptRef.current += 1
    loginBusyRef.current = false
    setIsProcessing(false)
    signupSamplesRef.current = []
    signupEyeSamplesRef.current = []
    loginSamplesRef.current = []
    loginEyeSamplesRef.current = []
    setScanMessage(faceIdleMessage(nextMode ?? mode))
  }, [mode])

  const switchMode = (next) => {
    setMode(next)
    signupDoneRef.current = false
    setSignupBlocked(false)
    resetScan(next)
  }

  const saveAndRedirect = useCallback(
    (data, message) => {
      setScanMessage(faceSuccessMessage(data.name, mode))
      setSession({ id: data.id, name: data.name, role: data.role })
      toast.success(message)
      redirectForRole(data.role)
    },
    [mode, toast],
  )

  const handleLoginFrame = useCallback(
    async ({ file, eyeEncoding }) => {
      if (loginBusyRef.current) return

      loginSamplesRef.current.push(file)
      loginEyeSamplesRef.current.push(eyeEncoding)
      const count = loginSamplesRef.current.length
      if (count < LOGIN_SAMPLE_COUNT) {
        setScanMessage(faceProgressMessage(count, LOGIN_SAMPLE_COUNT))
        return
      }

      const attempt = ++loginAttemptRef.current
      loginBusyRef.current = true
      setIsProcessing(true)
      setScanMessage(faceVerifyingMessage())

      try {
        const data = await faceLogin(loginSamplesRef.current, loginEyeSamplesRef.current)
        if (attempt !== loginAttemptRef.current) return

        loginBusyRef.current = false
        setIsProcessing(false)
        const msg =
          data.role === ROLE_ADMIN
            ? `Welcome, ${data.name}. Opening admin panel…`
            : data.message || `Welcome back, ${data.name}!`
        saveAndRedirect(data, msg)
      } catch (err) {
        if (attempt !== loginAttemptRef.current) return

        loginSamplesRef.current = []
        loginEyeSamplesRef.current = []
        loginBusyRef.current = false
        setIsProcessing(false)
        setScanMessage(parseFaceAuthError(err.message, 'login'))
      }
    },
    [saveAndRedirect],
  )

  const handleSignupFrame = useCallback(
    async ({ file, eyeEncoding }) => {
      if (!name.trim() || signupDoneRef.current || loginBusyRef.current) return

      signupSamplesRef.current.push(file)
      signupEyeSamplesRef.current.push(eyeEncoding)
      const count = signupSamplesRef.current.length
      if (count < SIGNUP_SAMPLE_COUNT) {
        setScanMessage(faceProgressMessage(count, SIGNUP_SAMPLE_COUNT))
        return
      }

      const attempt = ++loginAttemptRef.current
      loginBusyRef.current = true
      setIsProcessing(true)
      setScanMessage(faceCreatingAccountMessage())

      try {
        const data = await faceSignup(name, signupSamplesRef.current, signupEyeSamplesRef.current, 'user', null)
        if (attempt !== loginAttemptRef.current) return

        signupDoneRef.current = true
        loginBusyRef.current = false
        setIsProcessing(false)
        const msg =
          data.role === ROLE_ADMIN
            ? `Account created for ${data.name}. Opening admin panel…`
            : data.message || `Account created for ${data.name}!`
        saveAndRedirect(data, msg)
      } catch (err) {
        if (attempt !== loginAttemptRef.current) return

        signupSamplesRef.current = []
        signupEyeSamplesRef.current = []
        loginBusyRef.current = false
        setIsProcessing(false)
        const parsed = parseFaceAuthError(err.message, 'signup')
        if (parsed.type === 'blocked') {
          signupDoneRef.current = true
          setSignupBlocked(true)
        }
        setScanMessage(parsed)
        toast.error(parsed.title)
      }
    },
    [name, saveAndRedirect, toast],
  )

  const signupEnabled = mode === MODES.signup && name.trim().length > 0
  const onFrame = mode === MODES.login ? handleLoginFrame : handleSignupFrame
  const showBanner = scanMessage && scanMessage.type !== 'idle'
  const showRetry =
    (scanMessage?.type === 'error' || scanMessage?.type === 'blocked') && !isProcessing

  return (
    <div className="flex min-h-screen flex-col bg-[#0b1018] text-slate-200">
      <PageHeader title="Guardian OS" subtitle="Face & eye verification" theme="dark" />

      <main className="mx-auto flex w-full max-w-6xl flex-1 items-center px-4 py-6 sm:px-6 sm:py-8">
        <div className="grid w-full gap-6 lg:grid-cols-2 lg:items-stretch lg:gap-8">
          {/* left — eye auth visual */}
          <div className="flex flex-col justify-center rounded-2xl border border-white/10 bg-[#121a26] p-6 sm:p-8">
            <p className="text-center text-xs font-medium uppercase tracking-wider text-cyan-400">
              Biometric verification
            </p>
            <EyeAuthIllustration className="mx-auto mt-4 w-full max-w-[280px] sm:max-w-[320px]" />
            <h2 className="mt-6 text-center text-xl font-semibold text-slate-100 sm:text-2xl">
              Face &amp; iris recognition
            </h2>
            <p className="mx-auto mt-3 max-w-sm text-center text-sm leading-relaxed text-slate-400">
              Guardian scans your face and eye pattern locally, then unlocks your voice assistant
              dashboard — no passwords required.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {AUTH_TAGS.map((tag) => (
                <span
                  key={tag}
                  className="rounded-full border border-cyan-500/25 bg-cyan-500/10 px-3 py-1 text-xs font-medium text-cyan-300"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>

          {/* right — auth card */}
          <div className="flex flex-col">
            <div className="flex flex-1 flex-col rounded-2xl border border-white/10 bg-[#121a26] p-5 sm:p-6">
              <div className="mb-5 inline-flex w-full rounded-lg border border-white/10 bg-[#0b1018] p-1">
                <Tab active={mode === MODES.login} onClick={() => switchMode(MODES.login)}>
                  Sign in
                </Tab>
                <Tab active={mode === MODES.signup} onClick={() => switchMode(MODES.signup)}>
                  Sign up
                </Tab>
              </div>

              {mode === MODES.signup && (
                <div className="mb-4">
                  <label htmlFor="name" className="mb-2 block text-sm font-medium text-slate-300">
                    Full name
                  </label>
                  <input
                    id="name"
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Enter full name"
                    className="w-full rounded-lg border border-white/15 bg-[#0b1018] px-4 py-2.5 text-slate-100 placeholder:text-slate-500 outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/30"
                  />
                </div>
              )}

              <LiveFaceScanner
                key={mode}
                enabled={mode === MODES.login || signupEnabled}
                busy={isProcessing || signupBlocked}
                onFrame={onFrame}
                autoStart={false}
                scanIntervalMs={mode === MODES.login ? 150 : 350}
                captureQuality={mode === MODES.login ? 0.72 : 0.88}
                theme="dark"
              />

              {showBanner && (
                <div className="mt-4 space-y-3">
                  <ScanStatusBanner message={scanMessage} theme="dark" />
                  {showRetry && scanMessage?.action === 'signin' && (
                    <button
                      type="button"
                      onClick={() => switchMode(MODES.login)}
                      className="w-full cursor-pointer rounded-lg bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-cyan-500"
                    >
                      Switch to Sign in
                    </button>
                  )}
                  {showRetry && scanMessage?.type === 'error' && (
                    <button
                      type="button"
                      onClick={() => resetScan()}
                      className="w-full cursor-pointer rounded-lg border border-white/15 bg-[#0b1018] px-4 py-2.5 text-sm font-medium text-slate-200 hover:bg-white/5"
                    >
                      Try again
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

function Tab({ active, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex-1 cursor-pointer rounded-md px-4 py-2 text-sm font-medium transition ${
        active
          ? 'bg-cyan-600 text-white shadow-sm'
          : 'text-slate-400 hover:text-slate-200'
      }`}
    >
      {children}
    </button>
  )
}
