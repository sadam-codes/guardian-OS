/** User-facing copy for face signup / login flows. */

export function faceProgressMessage(current, total) {
  return {
    type: 'progress',
    title: `Scanning ${current} of ${total}`,
    detail: 'Hold still and look at the camera.',
    progress: { current, total },
  }
}

export function faceVerifyingMessage() {
  return {
    type: 'loading',
    title: 'Verifying your face',
    detail: 'This only takes a moment.',
  }
}

export function faceCreatingAccountMessage() {
  return {
    type: 'loading',
    title: 'Creating your account',
    detail: 'Saving your face profile…',
  }
}

export function faceIdleMessage(mode) {
  if (mode === 'signup') {
    return {
      type: 'idle',
      title: 'Ready to enroll',
      detail: 'Enter your name, open the camera, then hold still for 3 scans.',
    }
  }
  return {
    type: 'idle',
    title: 'Ready to sign in',
    detail: 'Open the camera and look straight at the screen.',
  }
}

export function faceSuccessMessage(name, mode) {
  if (mode === 'signup') {
    return {
      type: 'success',
      title: `Welcome, ${name}!`,
      detail: 'Account created. Redirecting you now…',
    }
  }
  return {
    type: 'success',
    title: `Welcome back, ${name}!`,
    detail: 'Face recognized. Opening your dashboard…',
  }
}

/**
 * Turn raw API / network errors into a structured banner message.
 */
export function parseFaceAuthError(message, mode = 'login') {
  const raw = (message || '').trim()
  const lower = raw.toLowerCase()

  if (!raw) {
    return {
      type: 'error',
      title: 'Something went wrong',
      detail: 'Please try again in a moment.',
    }
  }

  if (lower.includes('already registered as')) {
    const nameMatch = raw.match(/as '([^']+)'/i)
    const who = nameMatch?.[1]
    return {
      type: 'blocked',
      title: 'This face is already enrolled',
      detail: who
        ? `Registered as ${who}. Use Sign in instead of Sign up.`
        : 'Use Sign in — this face is already in the system.',
      action: 'signin',
    }
  }

  if (lower.includes('face is already enrolled') || lower.includes('already registered')) {
    return {
      type: 'blocked',
      title: 'This face is already enrolled',
      detail: 'Switch to Sign in — you already have an account with this face.',
      action: 'signin',
    }
  }

  if (lower.includes('name is already registered') || lower.includes('name is taken')) {
    return {
      type: 'blocked',
      title: 'Name already in use',
      detail: 'Pick another name or sign in if this is your account.',
    }
  }

  if (lower.includes('not recognized clearly') || lower.includes('better lighting')) {
    return {
      type: 'error',
      title: 'Could not confirm your face',
      detail: 'Use brighter lighting, remove sunglasses, and face the camera directly.',
    }
  }

  if (lower.includes('another enrolled face matches')) {
    return {
      type: 'error',
      title: 'Match too close to another account',
      detail:
        'Improve lighting and face the camera squarely so your profile wins clearly over other enrolled users.',
    }
  }

  if (lower.includes('not recognized') || lower.includes('sign up first')) {
    return {
      type: 'error',
      title: 'Face not recognized',
      detail:
        mode === 'login'
          ? 'No matching account found. Sign up first or try again closer to the camera.'
          : 'Try again with your face centered in the frame.',
    }
  }

  if (lower.includes('no face detected')) {
    return {
      type: 'error',
      title: 'No face detected',
      detail: 'Move closer, face the camera, and make sure your whole face is visible.',
    }
  }

  if (lower.includes('outdated') || lower.includes('sign up again')) {
    return {
      type: 'error',
      title: 'Face data needs refresh',
      detail: 'Ask an admin to delete your old account, then sign up again with the camera.',
    }
  }

  if (lower.includes('camera image required') || lower.includes('upload')) {
    return {
      type: 'error',
      title: 'No image captured',
      detail: 'Open the camera and wait until scanning starts.',
    }
  }

  return {
    type: 'error',
    title: mode === 'login' ? 'Sign in failed' : 'Sign up failed',
    detail: raw,
  }
}
