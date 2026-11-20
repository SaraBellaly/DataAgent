import { BarChart3, Gauge, Home, Square, Trash2, Trophy, Volume2, VolumeX } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'
import type { ExecutionResult } from '../api/types'
import { useConversation } from '../chat/useConversation'
import { Composer, type ComposerSubmit } from '../components/chat/Composer'
import { ExchangeView } from '../components/chat/ExchangeView'
import { MascotSlot } from '../components/mascot/MascotSlot'
import { Alert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { Spinner } from '../components/ui/Spinner'
import { useConversations } from '../layout/ConversationsContext'
import { ASSISTANT_NAME } from '../layout/Sidebar'
import { formatCell } from '../lib/format'
import { useVoice } from '../voice/VoiceContext'
import styles from './ChatPage.module.css'

/** Questions que l'agent sait réellement traiter sur DVF 2025 (vérifiées par les tests réels). */
const SUGGESTIONS = [
  { icon: Trophy, tint: 'peach', text: 'Quelles sont les 10 communes les plus chères au m² en 2025, avec au moins 100 ventes ?' },
  { icon: Home, tint: 'rose', text: 'Combien de maisons ont été vendues à Bordeaux en juin 2025 ?' },
  { icon: BarChart3, tint: 'lavender', text: 'Explique-moi cette requête SQL.', withSql: true },
  { icon: Gauge, tint: 'mint', text: 'Comment optimiser cette requête ?', withSql: true },
]

export function ChatPage() {
  const { user } = useAuth()
  const params = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const { refresh, remove } = useConversations()
  const routeId = params.id ? Number(params.id) : null

  const onCreated = useCallback(
    (id: number) => {
      navigate(`/conversations/${id}`, { replace: true })
      void refresh()
    },
    [navigate, refresh],
  )
  const conv = useConversation(Number.isFinite(routeId) ? routeId : null, onCreated)
  const [draft, setDraft] = useState<{ text: string; withSql?: boolean; key: number }>()
  const [confirmDelete, setConfirmDelete] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)
  const voice = useVoice()
  const spokenRef = useRef(new Set<string>())

  // Lecture automatique à voix haute : seulement pour une question DICTÉE au micro.
  // Question tapée au clavier : silence, le bouton « Écouter » reste disponible.
  useEffect(() => {
    const last = conv.exchanges[conv.exchanges.length - 1]
    if (!last || !last.key.startsWith('n') || !last.viaVoice) return
    const once = (id: string, text: string) => {
      if (spokenRef.current.has(id)) return
      spokenRef.current.add(id)
      voice.speak(text)
    }
    if (last.status === 'failed' && last.error) once(`${last.key}:e`, last.error.message)
    if (last.status === 'answered' && last.answer) once(`${last.key}:a`, last.answer.explication)
    if (last.execution.status === 'done' && last.execution.result) once(`${last.key}:r`, resultSummary(last.execution.result))
    if (last.execution.status === 'error' && last.execution.error) once(`${last.key}:x`, last.execution.error)
  }, [conv.exchanges, voice])

  // L'assistante se tait quand on ouvre une AUTRE conversation (pas quand celle-ci vient d'être créée),
  // et en quittant la page
  const { stop } = voice
  const shownId = conv.conversationId
  useEffect(() => {
    if (routeId !== null && routeId !== shownId) stop()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- seul le changement d'adresse compte
  }, [routeId])
  useEffect(() => stop, [stop])

  // « Nouvelle conversation » depuis la barre latérale, alors qu'on est déjà sur l'accueil
  const resetToken = (location.state as { reset?: number } | null)?.reset
  useEffect(() => {
    if (resetToken && routeId === null) {
      voice.stop()
      conv.reset()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resetToken])

  // Défilement vers le dernier échange
  const count = conv.exchanges.length
  const lastStatus = conv.exchanges[count - 1]?.status
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [count, lastStatus])

  const onSubmit = ({ question, sql, viaVoice }: ComposerSubmit) => {
    void conv.send(question, sql, viaVoice).then(() => void refresh())
  }

  async function deleteConversation() {
    voice.stop()
    if (!conv.conversationId) return
    await remove(conv.conversationId)
    setConfirmDelete(false)
    conv.reset()
    navigate('/', { replace: true })
  }

  const empty = count === 0 && !conv.loading && !conv.loadError
  const name = user?.email.split('@')[0] ?? ''

  if (empty) {
    return (
      <section className={styles.page}>
        <div className={styles.welcome}>
          <MascotSlot mood="welcome" size={230} />
          <h1 className={styles.title}>
            Bonjour {name && <span className={styles.name}>{name}</span>}, je suis{' '}
            <span className="gradient-text">{ASSISTANT_NAME}</span>
          </h1>
          <p className={styles.subtitle}>
            Posez une question sur le marché immobilier 2025 : je l’écris en SQL, vous la validez, puis je l’exécute en
            lecture seule. Je peux aussi expliquer et optimiser vos requêtes.
          </p>
          <div className={styles.composer}>
            <Composer onSubmit={onSubmit} draft={draft} />
          </div>
          <ul className={styles.suggestions} aria-label="Exemples de questions">
            {SUGGESTIONS.map(({ icon: Icon, tint, text, withSql }) => (
              <li key={text}>
                <button className={styles.pill} onClick={() => setDraft({ text, withSql, key: Date.now() })}>
                  <Icon size={16} className={styles[tint]} />
                  {text}
                </button>
              </li>
            ))}
          </ul>
        </div>
      </section>
    )
  }

  return (
    <section className={styles.chat}>
      <header className={styles.header}>
        <MascotSlot mood={conv.mood} size={52} speaking={voice.speaking} />
        <div className={styles.headerText}>
          <h1 title={conv.title ?? undefined}>{conv.title ?? 'Nouvelle conversation'}</h1>
          <p>{voice.speaking ? `${ASSISTANT_NAME} vous répond à voix haute…` : moodLabel(conv.mood)}</p>
        </div>
        {voice.supported && (
          <div className={styles.voiceControls}>
            {voice.speaking && (
              <Button size="sm" variant="secondary" icon={<Square size={14} />} onClick={voice.stop}>
                Arrêter
              </Button>
            )}
            <Button
              size="sm"
              variant="ghost"
              icon={voice.settings.enabled ? <Volume2 size={17} /> : <VolumeX size={17} />}
              onClick={() => {
                if (voice.settings.enabled) voice.stop()
                voice.updateSettings({ enabled: !voice.settings.enabled })
              }}
              aria-pressed={voice.settings.enabled}
              aria-label={voice.settings.enabled ? 'Couper la voix de l’assistante' : 'Activer la voix de l’assistante'}
              title={voice.settings.enabled ? 'Voix activée' : 'Voix coupée'}
            />
          </div>
        )}
        {conv.conversationId &&
          (confirmDelete ? (
            <div className={styles.confirm} role="alertdialog" aria-label="Confirmer la suppression">
              <span>Supprimer cette conversation et ses échanges ?</span>
              <Button size="sm" variant="ghost" onClick={() => setConfirmDelete(false)}>
                Annuler
              </Button>
              <Button size="sm" variant="danger" onClick={() => void deleteConversation()}>
                Supprimer
              </Button>
            </div>
          ) : (
            <Button size="sm" variant="ghost" icon={<Trash2 size={16} />} onClick={() => setConfirmDelete(true)} aria-label="Supprimer la conversation" />
          ))}
      </header>

      <div className={styles.thread}>
        <div className={styles.threadInner}>
          {conv.loading && (
            <p className={styles.loading}>
              <Spinner size={16} /> Chargement de la conversation…
            </p>
          )}
          {conv.loadError && <Alert tone="error">{conv.loadError}</Alert>}
          {conv.exchanges.map((exchange) => (
            <ExchangeView
              key={exchange.key}
              exchange={exchange}
              assistantName={ASSISTANT_NAME}
              onExecute={() => exchange.answer && void conv.execute(exchange.key, exchange.answer.history_id)}
              onPlan={(analyze) => exchange.answer && void conv.loadPlan(exchange.key, exchange.answer.history_id, analyze)}
              onRetry={() => conv.retry(exchange.key)}
            />
          ))}
          <div ref={endRef} />
        </div>
      </div>

      <footer className={styles.dock}>
        <Composer onSubmit={onSubmit} disabled={conv.pending} placeholder="Votre question de suivi…" />
        <p className={styles.disclaimer}>
          Les requêtes ne s’exécutent qu’après votre validation, en lecture seule. Données DVF 2025 et INSEE.
        </p>
      </footer>
    </section>
  )
}

/** Ce que l'assistante dit après une exécution : les valeurs d'une ligne unique, sinon le nombre de lignes. */
function resultSummary(result: ExecutionResult): string {
  if (result.nb_lignes === 0) return 'La requête n’a renvoyé aucune ligne.'
  if (result.nb_lignes === 1) {
    const parts = result.colonnes.slice(0, 4).map((c, i) => `${c} : ${formatCell(result.lignes[0][i])}`)
    return `Voici le résultat. ${parts.join(', ')}.`
  }
  return `La requête a renvoyé ${result.nb_lignes} lignes${result.tronque ? ', dont les deux cents premières' : ''}, affichées à l’écran.`
}

function moodLabel(mood: string): string {
  switch (mood) {
    case 'thinking':
      return `${ASSISTANT_NAME} réfléchit…`
    case 'processing':
      return `${ASSISTANT_NAME} interroge la base…`
    case 'error':
      return 'Une erreur est survenue'
    case 'success':
      return 'Prête pour la suite'
    default:
      return 'À votre écoute'
  }
}
