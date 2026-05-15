import { useCallback, useEffect, useRef, useState } from 'react'
import { faceLogin, faceSignup } from '../api/face'
import LiveFaceScanner from '../components/LiveFaceScanner'
import PageHeader from '../components/PageHeader'
import { useToast } from '../components/ToastProvider'
import { getSession, redirectForRole, setSession } from '../lib/session'

const MODES = { signup: 'signup', login: 'login' }
const ROLE_ADMIN = 'admin'

export default function HomePage() {
  const [mode, setMode] = useState(MODES.login)
  const [name, setName] = useState('')
  const [scanStatus, setScanStatus] = useState('scanning')
  const [hint, setHint] = useState('Open the camera, then look at the frame to sign in')
  const [lastError, setLastError] = useState('')
  const [cameraActive, setCameraActive] = useState(false)
  const signupDoneRef = useRef(false)
  const lastLoginErrorToastRef = useRef(0)
  const toast = useToast()

  useEffect(() => {
    const session = getSession()
    if (session?.role) {
      redirectForRole(session.role)
    }
  }, [])

  const switchMode = (next) => {
    setMode(next)
    setScanStatus('scanning')
    signupDoneRef.current = false
    setLastError('')
    setHint(
      next === MODES.login
        ? 'Open the camera, then look at the frame to sign in'
        : 'Enter your name, open the camera, then scan your face',
    )
  }

  const saveAndRedirect = useCallback(
    (data, message) => {
      setSession({ id: data.id, name: data.name, role: data.role })
      toast.success(message)
      redirectForRole(data.role)
    },
    [toast],
  )

  const handleLoginFrame = useCallback(
    async (file) => {
      try {
        const data = await faceLogin(file)
        const msg =
          data.role === ROLE_ADMIN
            ? `Welcome, ${data.name}. Opening admin panel…`
            : data.message || `Welcome back, ${data.name}!`
        saveAndRedirect(data, msg)
      } catch (err) {
        setScanStatus('scanning')
        const msg = err.message || 'Face not recognized'
        setLastError(msg)
        setHint('Recognizing your face…')
        const now = Date.now()
        if (now - lastLoginErrorToastRef.current > 6000) {
          lastLoginErrorToastRef.current = now
          toast.error(msg)
        }
      }
    },
    [saveAndRedirect, toast],
  )

  const handleSignupFrame = useCallback(
    async (file) => {
      if (!name.trim() || signupDoneRef.current) return

      try {
        const data = await faceSignup(name, file, 'user', null)
        signupDoneRef.current = true
        const msg =
          data.role === ROLE_ADMIN
            ? `Account created for ${data.name}. Opening admin panel…`
            : data.message || `Account created for ${data.name}!`
        saveAndRedirect(data, msg)
      } catch (err) {
        setScanStatus('error')
        const msg = err.message || 'Registration failed'
        setLastError(msg)
        setHint('Please adjust your position and try again')
        toast.error(msg)
        setTimeout(() => setScanStatus('scanning'), 2500)
      }
    },
    [name, saveAndRedirect, toast],
  )

  const signupEnabled = mode === MODES.signup && name.trim().length > 0
  const onFrame = mode === MODES.login ? handleLoginFrame : handleSignupFrame

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100">
      <PageHeader title="Guardian OS" subtitle="Secure face authentication" />

      <main className="mx-auto max-w-xl px-4 py-8 sm:px-6 sm:py-10">
        <div className="mb-8 text-center">
          <h2 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            {mode === MODES.login ? 'Sign in with your face' : 'Create your account'}
          </h2>
         
        </div>

        <Card>
          <div className="mb-6 inline-flex w-full rounded-lg bg-slate-100 p-1">
            <Tab active={mode === MODES.login} onClick={() => switchMode(MODES.login)}>
              Sign in
            </Tab>
            <Tab active={mode === MODES.signup} onClick={() => switchMode(MODES.signup)}>
              Sign up
            </Tab>
          </div>

          {mode === MODES.signup && (
            <div className="mb-6">
              <label htmlFor="name" className="mb-2 block text-sm font-medium text-slate-700">
                Full name
              </label>
              <input
                id="name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Enter full name"
                className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-slate-900 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20"
              />
              {!name.trim() && (
                <p className="mt-2 text-sm text-slate-500">Name is required before face enrollment.</p>
              )}
            </div>
          )}

          <LiveFaceScanner
            key={mode}
            enabled={mode === MODES.login || signupEnabled}
            paused={false}
            onFrame={onFrame}
            status={scanStatus}
            hint={hint}
            autoStart={false}
            onCameraReadyChange={setCameraActive}
          />
          <StatusBar
            scanning={scanStatus === 'scanning' && cameraActive}
            error={lastError}
            mode={mode}
            cameraActive={cameraActive}
          />
        </Card>
      </main>
    </div>
  )
}

function Card({ children }) {
  return (
    <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-sm shadow-slate-200/50 sm:p-8">
      {children}
    </div>
  )
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

function StatusBar({ scanning, error, mode, cameraActive }) {
  return null
}
  