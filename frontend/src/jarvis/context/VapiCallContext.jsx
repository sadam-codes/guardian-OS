import { createContext, useCallback, useContext, useMemo, useState } from 'react'

const VapiCallContext = createContext(null)

export function VapiCallProvider({ children }) {
  const [client, setClient] = useState(null)
  const [active, setActive] = useState(false)

  const registerClient = useCallback((vapiClient) => {
    setClient(vapiClient)
  }, [])

  const setCallActive = useCallback((on) => {
    setActive(Boolean(on))
  }, [])

  const speak = useCallback(
    (text) => {
      const line = (text || '').trim()
      if (!line || !client) return false
      if (active && typeof client.say === 'function') {
        client.say(line)
        return true
      }
      return false
    },
    [client, active],
  )

  const value = useMemo(
    () => ({ client, active, registerClient, setCallActive, speak }),
    [client, active, registerClient, setCallActive, speak],
  )

  return <VapiCallContext.Provider value={value}>{children}</VapiCallContext.Provider>
}

export function useVapiCall() {
  return useContext(VapiCallContext)
}
