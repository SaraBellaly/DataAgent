import { useCallback, useEffect, useRef, useState } from 'react'

import { ApiError } from '../api/client'
import { agentApi, conversationsApi } from '../api/endpoints'
import type { AgentAnswer, ExecutionResult, HistoryItem, Plan } from '../api/types'

export type Answer = Pick<AgentAnswer, 'history_id' | 'sql_propose' | 'explication' | 'recommandations'> &
  Partial<Pick<AgentAnswer, 'diagnostic_performance' | 'etapes' | 'duree_modele_ms' | 'duree_base_ms' | 'modele' | 'modele_secours'>>

export type Exchange = {
  key: string
  question: string
  createdAt: string
  status: 'pending' | 'answered' | 'failed'
  /** Question dictée au micro : la réponse est lue à voix haute automatiquement */
  viaVoice?: boolean
  answer?: Answer
  error?: { message: string; retryAfter?: number }
  execution: { status: 'idle' | 'running' | 'done' | 'error'; result?: ExecutionResult; error?: string; executedAt?: string }
  plan: { status: 'idle' | 'loading' | 'done' | 'error'; data?: Plan; error?: string }
}

/** État global de l'agent, pour la mascotte : accueil, réflexion, préparation, succès, erreur. */
export type AgentMood = 'welcome' | 'thinking' | 'processing' | 'success' | 'error'

/** Question envoyée à l'agent quand une requête SQL est jointe (relue à l'affichage). */
export const SQL_MARKER = '\n\nRequête :\n```sql\n'

export function composeQuestion(question: string, sql?: string): string {
  return sql ? `${question}${SQL_MARKER}${sql}\n\`\`\`` : question
}

export function splitQuestion(full: string): { text: string; sql: string | null } {
  const at = full.indexOf(SQL_MARKER)
  if (at < 0) return { text: full, sql: null }
  return { text: full.slice(0, at), sql: full.slice(at + SQL_MARKER.length).replace(/\n?```\s*$/, '') }
}

function fromHistory(item: HistoryItem): Exchange {
  return {
    key: `h${item.id}`,
    question: item.question,
    createdAt: item.created_at,
    status: 'answered',
    answer: {
      history_id: item.id,
      sql_propose: item.sql_propose,
      explication: item.explication ?? '',
      recommandations: item.recommandations,
    },
    execution: item.resultat
      ? { status: 'done', result: item.resultat, executedAt: item.executed_at ?? undefined }
      : { status: 'idle' },
    plan: { status: 'idle' },
  }
}

// Détails non conservés par le serveur (diagnostic, étapes, temps) : gardés le temps de la session
const sessionDetails = new Map<number, Partial<Answer>>()

export function useConversation(routeId: number | null, onConversationCreated: (id: number) => void) {
  const [conversationId, setConversationId] = useState<number | null>(routeId)
  const [title, setTitle] = useState<string | null>(null)
  const [exchanges, setExchanges] = useState<Exchange[]>([])
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const ownIdRef = useRef<number | null>(routeId)
  const abortRef = useRef<AbortController | null>(null)

  // Ouverture d'une conversation existante (ou retour à une conversation vide)
  useEffect(() => {
    if (routeId !== null && routeId === ownIdRef.current && exchanges.length > 0) return // déjà affichée
    abortRef.current?.abort()
    ownIdRef.current = routeId
    setConversationId(routeId)
    setLoadError(null)
    if (routeId === null) {
      setExchanges([])
      setTitle(null)
      return
    }
    let cancelled = false
    setLoading(true)
    conversationsApi
      .get(routeId)
      .then((detail) => {
        if (cancelled) return
        setTitle(detail.titre)
        setExchanges(
          detail.echanges.map((item) => {
            const exchange = fromHistory(item)
            const extra = sessionDetails.get(item.id)
            return extra && exchange.answer ? { ...exchange, answer: { ...exchange.answer, ...extra } } : exchange
          }),
        )
      })
      .catch((e: unknown) => !cancelled && setLoadError(e instanceof ApiError ? e.message : 'Conversation introuvable.'))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [routeId])

  const update = useCallback((key: string, change: (e: Exchange) => Exchange) => {
    setExchanges((list) => list.map((e) => (e.key === key ? change(e) : e)))
  }, [])

  const ask = useCallback(
    async (key: string, question: string) => {
      const controller = new AbortController()
      abortRef.current = controller
      try {
        const answer = await agentApi.ask(question, ownIdRef.current ?? undefined, controller.signal)
        sessionDetails.set(answer.history_id, {
          diagnostic_performance: answer.diagnostic_performance,
          etapes: answer.etapes,
          duree_modele_ms: answer.duree_modele_ms,
          duree_base_ms: answer.duree_base_ms,
          modele: answer.modele,
          modele_secours: answer.modele_secours,
        })
        update(key, (e) => ({ ...e, status: 'answered', answer, error: undefined }))
        if (ownIdRef.current === null) {
          ownIdRef.current = answer.conversation_id
          setConversationId(answer.conversation_id)
          setTitle(question.split(SQL_MARKER)[0].slice(0, 120))
          onConversationCreated(answer.conversation_id)
        }
        return answer
      } catch (e) {
        if ((e as Error).name === 'AbortError') return null
        const error = e instanceof ApiError ? { message: e.message, retryAfter: e.retryAfter } : { message: 'La question n’a pas pu être traitée.' }
        update(key, (x) => ({ ...x, status: 'failed', error }))
        return null
      }
    },
    [onConversationCreated, update],
  )

  const send = useCallback(
    (question: string, sql?: string, viaVoice = false) => {
      const full = composeQuestion(question, sql)
      const key = `n${Date.now()}`
      setExchanges((list) => [
        ...list,
        { key, question: full, createdAt: new Date().toISOString(), status: 'pending', viaVoice, execution: { status: 'idle' }, plan: { status: 'idle' } },
      ])
      return ask(key, full)
    },
    [ask],
  )

  const retry = useCallback(
    (key: string) => {
      const exchange = exchanges.find((e) => e.key === key)
      if (!exchange) return
      update(key, (e) => ({ ...e, status: 'pending', error: undefined }))
      void ask(key, exchange.question)
    },
    [ask, exchanges, update],
  )

  /** Validation par l'utilisateur : exécution en lecture seule (rôle analyst_ro). */
  const execute = useCallback(
    async (key: string, historyId: number) => {
      update(key, (e) => ({ ...e, execution: { status: 'running' } }))
      try {
        const result = await agentApi.execute(historyId)
        update(key, (e) => ({ ...e, execution: { status: 'done', result, executedAt: new Date().toISOString() } }))
        return true
      } catch (e) {
        update(key, (x) => ({ ...x, execution: { status: 'error', error: e instanceof ApiError ? e.message : 'L’exécution a échoué.' } }))
        return false
      }
    },
    [update],
  )

  const loadPlan = useCallback(
    async (key: string, historyId: number, analyze = false) => {
      update(key, (e) => ({ ...e, plan: { ...e.plan, status: 'loading', error: undefined } }))
      try {
        const data = await agentApi.plan(historyId, analyze)
        update(key, (e) => ({ ...e, plan: { status: 'done', data } }))
      } catch (e) {
        update(key, (x) => ({ ...x, plan: { status: 'error', error: e instanceof ApiError ? e.message : 'Plan indisponible.' } }))
      }
    },
    [update],
  )

  /** Nouvelle conversation : on repart d'un écran vide. */
  const reset = useCallback(() => {
    abortRef.current?.abort()
    ownIdRef.current = null
    setConversationId(null)
    setTitle(null)
    setExchanges([])
    setLoadError(null)
  }, [])

  const pending = exchanges.some((e) => e.status === 'pending')
  const running = exchanges.some((e) => e.execution.status === 'running' || e.plan.status === 'loading')
  const last = exchanges[exchanges.length - 1]
  const mood: AgentMood = pending
    ? 'thinking'
    : running
      ? 'processing'
      : !last
        ? 'welcome'
        : last.status === 'failed' || last.execution.status === 'error'
          ? 'error'
          : 'success'

  return { conversationId, title, exchanges, loading, loadError, pending, mood, send, retry, execute, loadPlan, reset }
}
