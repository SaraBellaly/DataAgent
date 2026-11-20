import {
  AlertTriangle,
  CircleAlert,
  Gauge,
  Lightbulb,
  Play,
  RefreshCw,
  ScrollText,
  ShieldCheck,
  Timer,
  Volume2,
} from 'lucide-react'
import { motion } from 'motion/react'

import type { Exchange } from '../../chat/useConversation'
import { splitQuestion } from '../../chat/useConversation'
import { formatDuration } from '../../lib/format'
import { useVoice } from '../../voice/VoiceContext'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Logo'
import { Spinner } from '../ui/Spinner'
import styles from './ExchangeView.module.css'
import { Markdown } from './Markdown'
import { ResultView } from './ResultView'
import { SqlBlock } from './SqlBlock'
import { ThinkingIndicator } from './ThinkingIndicator'

type Props = {
  exchange: Exchange
  assistantName: string
  onExecute: () => void
  onPlan: (analyze: boolean) => void
  onRetry: () => void
}

const appear = { initial: { opacity: 0, y: 10 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.32, ease: [0.22, 1, 0.36, 1] as const } }

/** Un échange : question, puis cartes distinctes pour la réponse, le SQL, la validation, les résultats… */
export function ExchangeView({ exchange, assistantName, onExecute, onPlan, onRetry }: Props) {
  const voice = useVoice()
  const { text, sql: attachedSql } = splitQuestion(exchange.question)
  const { answer, execution, plan } = exchange

  return (
    <article className={styles.exchange}>
      {/* Question de l'utilisateur */}
      <motion.div className={styles.userRow} {...appear}>
        <div className={styles.userBubble}>
          <p>{text}</p>
          {attachedSql && <SqlBlock sql={attachedSql} label="Requête jointe" />}
        </div>
      </motion.div>

      <div className={styles.assistantRow}>
        <span className={styles.avatar} aria-hidden="true">
          <Badge size={34} />
        </span>

        <div className={styles.assistantColumn}>
          {exchange.status === 'pending' && <ThinkingIndicator name={assistantName} />}

          {exchange.status === 'failed' && exchange.error && (
            <motion.div className={`${styles.card} ${styles.errorCard}`} {...appear}>
              <div className={styles.cardTitle}>
                <CircleAlert size={17} /> Je n’ai pas pu répondre
              </div>
              <p>{exchange.error.message}</p>
              <p className={styles.small}>Aucune réponse n’a été inventée et rien n’a été enregistré dans l’historique.</p>
              <div>
                <Button variant="secondary" size="sm" icon={<RefreshCw size={15} />} onClick={onRetry}>
                  Réessayer
                </Button>
              </div>
            </motion.div>
          )}

          {answer && (
            <>
              {/* Explication */}
              <motion.section className={styles.card} {...appear} aria-label="Explication">
                <Markdown text={answer.explication} />
                <div className={styles.metaRow}>
                {(answer.duree_modele_ms !== undefined || answer.etapes) && (
                  <p className={styles.meta}>
                    {answer.etapes && answer.etapes.length > 0 && <>Démarche : {answer.etapes.join(' → ')} · </>}
                    {answer.duree_modele_ms !== undefined && <>modèle {formatDuration(answer.duree_modele_ms)}</>}
                    {answer.duree_base_ms !== undefined && <> · base {formatDuration(answer.duree_base_ms)}</>}
                    {answer.modele_secours && (
                      <span className={styles.fallback} title={`Quota du modèle principal atteint : réponse de ${answer.modele}`}>
                        {' '}· modèle de secours ({answer.modele?.split('/').pop()})
                      </span>
                    )}
                  </p>
                )}
                {voice.supported && (
                  <button
                    type="button"
                    className={styles.listen}
                    onClick={() => voice.speak(answer.explication, { force: true })}
                    aria-label="Écouter la réponse"
                  >
                    <Volume2 size={14} /> Écouter
                  </button>
                )}
                </div>
              </motion.section>

              {/* SQL proposé et validation */}
              {answer.sql_propose && (
                <motion.section className={styles.card} {...appear} transition={{ ...appear.transition, delay: 0.06 }} aria-label="Requête SQL proposée">
                  <div className={styles.cardTitle}>
                    <ScrollText size={17} /> Requête proposée
                  </div>
                  <SqlBlock sql={answer.sql_propose} />
                  {answer.diagnostic_performance && (
                    <div className={styles.warning}>
                      <AlertTriangle size={16} />
                      <span>{answer.diagnostic_performance}</span>
                    </div>
                  )}

                  {execution.status !== 'done' && (
                    <div className={styles.validate}>
                      <p className={styles.safety}>
                        <ShieldCheck size={15} />
                        <span>
                          Une seule instruction <code>SELECT</code>, vérifiée. Elle ne s’exécute qu’après votre validation, en
                          lecture seule (30 s au plus).
                        </span>
                      </p>
                      <Button
                        icon={<Play size={16} />}
                        loading={execution.status === 'running'}
                        onClick={onExecute}
                      >
                        {execution.status === 'running' ? 'Exécution…' : 'Valider et exécuter'}
                      </Button>
                    </div>
                  )}
                  {execution.status === 'error' && <p className={styles.inlineError}>{execution.error}</p>}
                </motion.section>
              )}

              {/* Résultats */}
              {execution.status === 'done' && execution.result && (
                <motion.section className={styles.card} {...appear} aria-label="Résultats">
                  <div className={styles.cardTitle}>
                    <Timer size={17} /> Résultats
                  </div>
                  <ResultView result={execution.result} />
                </motion.section>
              )}

              {/* Plan d'exécution */}
              {answer.sql_propose && (
                <motion.section className={`${styles.card} ${styles.soft}`} {...appear} aria-label="Plan d'exécution">
                  <div className={styles.planHeader}>
                    <div className={styles.cardTitle}>
                      <Gauge size={17} /> Plan d’exécution (EXPLAIN)
                    </div>
                    <div className={styles.planActions}>
                      <Button variant="secondary" size="sm" onClick={() => onPlan(false)} disabled={plan.status === 'loading'}>
                        Plan estimé
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onPlan(true)}
                        disabled={plan.status === 'loading'}
                        title="EXPLAIN ANALYZE exécute la requête pour mesurer les temps réels"
                      >
                        Mesurer (ANALYZE)
                      </Button>
                    </div>
                  </div>
                  {plan.status === 'loading' && (
                    <p className={styles.small}>
                      <Spinner size={14} /> Analyse du plan…
                    </p>
                  )}
                  {plan.status === 'error' && <p className={styles.inlineError}>{plan.error}</p>}
                  {plan.status === 'done' && plan.data && (
                    <>
                      {plan.data.diagnostic_performance && (
                        <div className={styles.warning}>
                          <AlertTriangle size={16} />
                          <span>{plan.data.diagnostic_performance}</span>
                        </div>
                      )}
                      <SqlBlock sql={plan.data.plan} label={plan.data.analyze ? 'EXPLAIN ANALYZE (mesuré)' : 'EXPLAIN (estimé)'} />
                    </>
                  )}
                </motion.section>
              )}

              {/* Suggestions d'optimisation */}
              {answer.recommandations.length > 0 && (
                <motion.section className={`${styles.card} ${styles.recoCard}`} {...appear} aria-label="Suggestions d'optimisation">
                  <div className={styles.cardTitle}>
                    <Lightbulb size={17} /> Suggestions d’optimisation
                  </div>
                  <ul className={styles.recos}>
                    {answer.recommandations.map((r) => (
                      <li key={r}>
                        <Markdown text={r} />
                      </li>
                    ))}
                  </ul>
                  <p className={styles.small}>À valider par un DBA : {assistantName} ne les applique jamais elle-même.</p>
                </motion.section>
              )}
            </>
          )}
        </div>
      </div>
    </article>
  )
}
