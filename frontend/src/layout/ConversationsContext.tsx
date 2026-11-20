import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { conversationsApi } from '../api/endpoints'
import type { Conversation } from '../api/types'

type Value = {
  conversations: Conversation[]
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
  remove: (id: number) => Promise<void>
}

const ConversationsContext = createContext<Value | null>(null)

/** Liste des conversations de l'utilisateur, partagée entre la barre latérale et les pages. */
export function ConversationsProvider({ children }: { children: ReactNode }) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      setConversations(await conversationsApi.list())
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  const remove = useCallback(async (id: number) => {
    await conversationsApi.remove(id)
    setConversations((list) => list.filter((c) => c.id !== id))
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const value = useMemo(() => ({ conversations, loading, error, refresh, remove }), [conversations, loading, error, refresh, remove])
  return <ConversationsContext.Provider value={value}>{children}</ConversationsContext.Provider>
}

export function useConversations(): Value {
  const ctx = useContext(ConversationsContext)
  if (!ctx) throw new Error('useConversations doit être utilisé dans <ConversationsProvider>')
  return ctx
}
