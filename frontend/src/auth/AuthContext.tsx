import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { ApiError, SESSION_EXPIRED_EVENT } from '../api/client'
import { authApi } from '../api/endpoints'
import type { User } from '../api/types'

type Status = 'loading' | 'authenticated' | 'anonymous'

type AuthContextValue = {
  status: Status
  user: User | null
  /** Message affiché sur l'écran de connexion (session expirée, compte supprimé…) */
  notice: string | null
  /** Écran où revenir quand la session prend fin (inscription après suppression du compte) */
  exitTo: '/connexion' | '/inscription'
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  deleteAccount: () => Promise<void>
  clearNotice: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [status, setStatus] = useState<Status>('loading')
  const [notice, setNotice] = useState<string | null>(null)
  const [exitTo, setExitTo] = useState<'/connexion' | '/inscription'>('/connexion')

  // Au chargement : la session (cookie HttpOnly) est-elle encore valide côté serveur ?
  useEffect(() => {
    authApi
      .me()
      .then((u) => {
        setUser(u)
        setStatus('authenticated')
      })
      .catch(() => setStatus('anonymous'))
  }, [])

  // Session expirée pendant l'utilisation : retour à l'écran de connexion avec un message clair
  useEffect(() => {
    const onExpired = () => {
      setUser(null)
      setStatus('anonymous')
      setNotice('Votre session a expiré. Reconnectez-vous pour continuer.')
    }
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired)
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired)
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    await authApi.login(email, password)
    const u = await authApi.me()
    setUser(u)
    setStatus('authenticated')
    setNotice(null)
    setExitTo('/connexion')
  }, [])

  const register = useCallback(async (email: string, password: string) => {
    await authApi.register(email, password)
    setNotice('Compte créé. Connectez-vous pour commencer.')
  }, [])

  const logout = useCallback(async () => {
    try {
      await authApi.logout()
    } catch (error) {
      if (!(error instanceof ApiError)) throw error
    }
    setUser(null)
    setStatus('anonymous')
  }, [])

  const deleteAccount = useCallback(async () => {
    await authApi.deleteAccount()
    setExitTo('/inscription')   // fiche, écran 4 : retour à l'écran d'inscription
    setUser(null)
    setStatus('anonymous')
    setNotice('Votre compte, vos sessions et tout votre historique ont été supprimés.')
  }, [])

  const value = useMemo(
    () => ({ status, user, notice, exitTo, login, register, logout, deleteAccount, clearNotice: () => setNotice(null) }),
    [status, user, notice, exitTo, login, register, logout, deleteAccount],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth doit être utilisé dans <AuthProvider>')
  return ctx
}
