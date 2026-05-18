/** Decorative eye + iris-scan graphic for the login hero panel */
export default function EyeAuthIllustration({ className = '' }) {
  return (
    <svg
      viewBox="0 0 400 400"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden
    >
      <defs>
        <radialGradient id="irisGlow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#22d3ee" stopOpacity="0.35" />
          <stop offset="70%" stopColor="#0891b2" stopOpacity="0.12" />
          <stop offset="100%" stopColor="#0b1018" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="scanLine" x1="0" y1="0" x2="400" y2="0">
          <stop offset="0%" stopColor="#22d3ee" stopOpacity="0" />
          <stop offset="50%" stopColor="#22d3ee" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#22d3ee" stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* outer scan rings */}
      <circle cx="200" cy="200" r="168" stroke="#22d3ee" strokeOpacity="0.12" strokeWidth="1" />
      <circle cx="200" cy="200" r="140" stroke="#22d3ee" strokeOpacity="0.18" strokeWidth="1" strokeDasharray="6 10" />
      <circle cx="200" cy="200" r="112" stroke="#22d3ee" strokeOpacity="0.25" strokeWidth="1" />

      {/* corner brackets */}
      <path d="M72 72h40v40M328 72h-40v40M72 328h40v-40M328 328h-40v-40" stroke="#22d3ee" strokeOpacity="0.4" strokeWidth="2" strokeLinecap="round" />

      {/* eye outline */}
      <path
        d="M60 200c0-55 62-100 140-100s140 45 140 100-62 100-140 100S60 255 60 200z"
        stroke="#64748b"
        strokeWidth="2"
        fill="#121a26"
      />
      <ellipse cx="200" cy="200" rx="72" ry="72" fill="url(#irisGlow)" />
      <circle cx="200" cy="200" r="52" stroke="#22d3ee" strokeOpacity="0.5" strokeWidth="1.5" fill="#0b1018" />
      <circle cx="200" cy="200" r="28" fill="#164e63" stroke="#22d3ee" strokeWidth="2" />
      <circle cx="200" cy="200" r="12" fill="#0b1018" />
      <circle cx="212" cy="188" r="5" fill="#22d3ee" fillOpacity="0.7" />

      {/* iris mesh */}
      {[0, 30, 60, 90, 120, 150].map((deg) => (
        <line
          key={deg}
          x1="200"
          y1="200"
          x2={200 + 48 * Math.cos((deg * Math.PI) / 180)}
          y2={200 + 48 * Math.sin((deg * Math.PI) / 180)}
          stroke="#22d3ee"
          strokeOpacity="0.2"
          strokeWidth="1"
        />
      ))}

      {/* horizontal scan beam */}
      <rect x="48" y="196" width="304" height="8" fill="url(#scanLine)" opacity="0.55" rx="4">
        <animate attributeName="y" values="120;280;120" dur="4s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.3;0.7;0.3" dur="4s" repeatCount="indefinite" />
      </rect>

      {/* eye tracking dots */}
      <circle cx="128" cy="168" r="4" fill="#22d3ee" fillOpacity="0.8">
        <animate attributeName="opacity" values="0.4;1;0.4" dur="2s" repeatCount="indefinite" />
      </circle>
      <circle cx="272" cy="232" r="4" fill="#22d3ee" fillOpacity="0.8">
        <animate attributeName="opacity" values="1;0.4;1" dur="2s" repeatCount="indefinite" />
      </circle>
    </svg>
  )
}
