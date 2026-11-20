import { Gauge, Lightbulb, Wand2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { ApiError } from '../api/client'
import { agentApi } from '../api/endpoints'
import { composeQuestion } from '../chat/useConversation'
import { ThinkingIndicator } from '../components/chat/ThinkingIndicator'
import { MascotSlot } from '../components/mascot/MascotSlot'
import { Alert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { useConversations } from '../layout/ConversationsContext'
import { ASSISTANT_NAME } from '../layout/Sidebar'
import styles from './OptimizerPage.module.css'
import page from './Page.module.css'

const GOALS = [
  { id: 'lent', label: 'Pourquoi est-elle lente ?', question: 'Pourquoi cette requête est-elle lente ? Appuie-toi sur son plan d’exécution.' },
  { id: 'optimiser', label: 'Comment l’optimiser ?', question: 'Comment optimiser cette requête ? Propose des index ou une réécriture, à valider.' },
  { id: 'expliquer', label: 'Que fait-elle ?', question: 'Explique-moi ce que fait cette requête, étape par étape.' },
]

/** Exemples réels de la base : la vue recalculée (lente) et un filtre sans index. */
const EXAMPLES = [
  { label: 'Vue des prix recalculée', sql: "SELECT * FROM immo.v_prix_m2_commune WHERE code_commune = '33063'" },
  { label: 'Filtre sur une période', sql: "SELECT count(*) FROM immo.dvf_mutations\nWHERE date_mutation BETWEEN '2025-06-01' AND '2025-06-30'" },
  { label: 'Agrégat par commune', sql: 'SELECT code_commune, count(DISTINCT id_mutation) AS ventes\nFROM immo.dvf_mutations\nGROUP BY code_commune\nORDER BY ventes DESC\nLIMIT 10' },
]

export function OptimizerPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const { refresh } = useConversations()
  const initialSql = (location.state as { sql?: string } | null)?.sql ?? ''
  const [sql, setSql] = useState(initialSql)
  const [goal, setGoal] = useState(GOALS[0].id)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (!sql.trim()) return
    setBusy(true)
    setError(null)
    try {
      const question = GOALS.find((g) => g.id === goal)!.question
      const answer = await agentApi.ask(composeQuestion(question, sql.trim()))
      void refresh()
      navigate(`/conversations/${answer.conversation_id}`)   // la réponse s'affiche dans la conversation
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'L’analyse a échoué.')
      setBusy(false)
    }
  }

  return (
    <section className={page.page}>
      <div className={page.inner}>
        <header className={page.header}>
          <MascotSlot mood={busy ? 'thinking' : error ? 'error' : 'welcome'} size={64} />
          <div className={page.headerText}>
            <h1>SQL Optimizer</h1>
            <p>
              Collez une requête : {ASSISTANT_NAME} lit son plan d’exécution (<code>EXPLAIN</code>, sans l’exécuter), explique
              sa lenteur et propose des index ou des réécritures. Rien n’est jamais appliqué automatiquement.
            </p>
          </div>
        </header>

        <form className={page.card} onSubmit={onSubmit}>
          <div className={page.cardHeader}>
            <h2 className={page.cardTitle}>
              <Gauge size={17} /> Requête à analyser
            </h2>
            <div className={styles.examples}>
              {EXAMPLES.map((ex) => (
                <button key={ex.label} type="button" className={styles.example} onClick={() => setSql(ex.sql)}>
                  {ex.label}
                </button>
              ))}
            </div>
          </div>

          <textarea
            className={styles.editor}
            value={sql}
            onChange={(e) => setSql(e.target.value)}
            placeholder="SELECT … FROM immo.dvf_mutations WHERE …"
            spellCheck={false}
            rows={9}
            maxLength={2800}
            aria-label="Requête SQL à analyser"
          />

          <fieldset className={styles.goals}>
            <legend className={page.muted}>Ce que vous voulez savoir</legend>
            {GOALS.map((g) => (
              <label key={g.id} className={`${styles.goal} ${goal === g.id ? styles.goalOn : ''}`}>
                <input type="radio" name="goal" value={g.id} checked={goal === g.id} onChange={() => setGoal(g.id)} />
                {g.label}
              </label>
            ))}
          </fieldset>

          {error && <Alert tone="error">{error}</Alert>}
          {busy && <ThinkingIndicator name={ASSISTANT_NAME} />}

          <div className={styles.actions}>
            <p className={page.muted}>
              <Lightbulb size={14} /> Une requête de <code>pg_stat_statements</code> avec <code>$1</code> reçoit un plan générique.
            </p>
            <Button type="submit" icon={<Wand2 size={16} />} loading={busy} disabled={!sql.trim()}>
              Analyser
            </Button>
          </div>
        </form>
      </div>
    </section>
  )
}
