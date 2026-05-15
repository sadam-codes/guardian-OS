import { useCallback, useEffect, useRef, useState } from 'react'
import { faceLogin, faceSignup } from '../api/face'
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
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100">
      <PageHeader title="Guardian OS" subtitle="Face & eye verification" />

      <main className="mx-auto max-w-xl px-4 py-8 sm:px-6 sm:py-10">
        <div className="mb-6 text-center">
          <h2 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            {mode === MODES.login ? 'Sign in with your face' : 'Create your account'}
          </h2>
        </div>

        <Card>
          <div className="mb-4 inline-flex w-full rounded-lg bg-slate-100 p-1">
            <Tab active={mode === MODES.login} onClick={() => switchMode(MODES.login)}>
              Sign in
            </Tab>
            <Tab active={mode === MODES.signup} onClick={() => switchMode(MODES.signup)}>
              Sign up
            </Tab>
          </div>

          {mode === MODES.signup && (
            <div className="mb-4">
              <label htmlFor="name" className="mb-2 block text-sm font-medium text-slate-700">
                Full name
              </label>
              <input
                id="name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Enter full name"
                className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-slate-900 shadow-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20"
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
          />

          {showBanner && (
            <div className="mt-4 space-y-3">
              <ScanStatusBanner message={scanMessage} />
              {showRetry && scanMessage?.action === 'signin' && (
                <button
                  type="button"
                  onClick={() => switchMode(MODES.login)}
                  className="w-full cursor-pointer rounded-xl bg-indigo-600 px-4 py-3 text-sm font-semibold text-white hover:bg-indigo-700"
                >
                  Switch to Sign in
                </button>
              )}
              {showRetry && scanMessage?.type === 'error' && (
                <button
                  type="button"
                  onClick={() => resetScan()}
                  className="w-full cursor-pointer rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm font-semibold text-slate-800 hover:bg-slate-50"
                >
                  Try again
                </button>
              )}
            </div>
          )}
        </Card>
      </main>
    </div>
  )
}

function Card({ children }) {
  return <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-sm sm:p-8">{children}</div>
}

function Tab({ active, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex-1 cursor-pointer rounded-md px-5 py-2 text-sm font-medium transition ${
        active ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-600 hover:text-slate-900'
      }`}
    >
      {children}
    </button>
  )
}

