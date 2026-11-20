import { Gauge, History, MessageCircle, RefreshCw, ScrollText } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { ApiError } from '../api/client'
import { dashboardApi } from '../api/endpoints'
import type { Dashboard } from '../api/types'
import { splitQuestion } from '../chat/useConversation'
import { MascotSlot } from '../components/mascot/MascotSlot'
import { Alert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { Spinner } from '../components/ui/Spinner'
import { formatDateTime, formatDuration, formatNumber } from '../lib/format'
import styles from './DashboardPage.module.css'
import page from './Page.module.css'

/** Tableau de bord : uniquement des données réelles (statistiques de l'utilisateur, pg_stat_statements). */
export function DashboardPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<Dashboard | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setData(await dashboardApi.get())
      setError(null)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Tableau de bord indisponible.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const tiles = data
    ? [
        { label: 'Conversations', value: data.nb_conversations },
        { label: 'Questions posées', value: data.nb_questions },
        { label: 'Requêtes proposées', value: data.nb_requetes_proposees },
        { label: 'Requêtes exécutées', value: data.nb_requetes_executees, hint: 'après votre validation' },
        { label: 'Avec recommandations', value: data.nb_avec_recommandations },
      ]
    : []

  return (
    <section className={page.page}>
      <div className={page.inner}>
        <header className={page.header}>
          <MascotSlot mood={error ? 'error' : loading ? 'processing' : 'success'} size={64} />
          <div className={page.headerText}>
            <h1>Tableau de bord</h1>
            <p>
              Votre activité et les requêtes les plus coûteuses de la base.
              {data?.derniere_activite && <> Dernière activité : {formatDateTime(data.derniere_activite)}.</>}
            </p>
          </div>
          <Button variant="secondary" size="sm" icon={<RefreshCw size={15} />} onClick={() => void load()} loading={loading}>
            Actualiser
          </Button>
        </header>

        {error && <Alert tone="error">{error}</Alert>}
        {!data && loading && (
          <p className={page.muted}>
            <Spinner size={15} /> Chargement…
          </p>
        )}

        {data && (
          <>
            <div className={styles.tiles}>
              {tiles.map((t) => (
                <div key={t.label} className={styles.tile}>
                  <span className={styles.tileValue}>{formatNumber(t.value)}</span>
                  <span className={styles.tileLabel}>{t.label}</span>
                  {t.hint && <span className={styles.tileHint}>{t.hint}</span>}
                </div>
              ))}
            </div>

            <div className={page.grid2}>
              <section className={page.card} aria-label="Dernières questions">
                <div className={page.cardHeader}>
                  <h2 className={page.cardTitle}>
                    <History size={17} /> Dernières questions
                  </h2>
                  <Link to="/historique" className={styles.more}>
                    Tout l’historique
                  </Link>
                </div>
                {data.dernieres_questions.length === 0 ? (
                  <p className={page.muted}>
                    Aucune question pour l’instant. <Link to="/">Posez votre première question</Link>.
                  </p>
                ) : (
                  <ul className={styles.recent}>
                    {data.dernieres_questions.map((q) => (
                      <li key={q.id}>
                        <Link to={q.conversation_id ? `/conversations/${q.conversation_id}` : '/historique'}>
                          <MessageCircle size={15} />
                          <span className={styles.recentText}>{splitQuestion(q.question).text}</span>
                          <span className={styles.recentMeta}>
                            {q.executed_at ? 'exécutée' : q.sql_propose ? 'SQL proposé' : 'réponse'} · {formatDateTime(q.created_at)}
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section className={page.card} aria-label="Ce que mesure ce tableau">
                <h2 className={page.cardTitle}>
                  <ScrollText size={17} /> À propos de ces chiffres
                </h2>
                <ul className={styles.notes}>
                  <li>Les compteurs ne portent que sur <strong>votre</strong> compte.</li>
                  <li>
                    Les requêtes coûteuses viennent de <code>pg_stat_statements</code> : toute l’activité de la base, en
                    lecture seule, sans les requêtes internes de l’application.
                  </li>
                  <li>Une requête n’est exécutée qu’après votre validation, en lecture seule (30 s au plus).</li>
                </ul>
              </section>
            </div>

            <section className={page.card} aria-label="Requêtes les plus coûteuses">
              <div className={page.cardHeader}>
                <h2 className={page.cardTitle}>
                  <Gauge size={17} /> Requêtes les plus coûteuses (temps cumulé)
                </h2>
              </div>
              {data.requetes_couteuses.length === 0 ? (
                <p className={page.muted}>Aucune statistique disponible pour l’instant.</p>
              ) : (
                <div className={styles.tableScroll}>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th>Requête</th>
                        <th className={styles.num}>Appels</th>
                        <th className={styles.num}>Temps total</th>
                        <th className={styles.num}>Temps moyen</th>
                        <th aria-label="Action" />
                      </tr>
                    </thead>
                    <tbody>
                      {data.requetes_couteuses.map((q, i) => (
                        <tr key={i}>
                          <td className={styles.sql} title={q.requete}>
                            {q.requete}
                          </td>
                          <td className={styles.num}>{formatNumber(q.appels)}</td>
                          <td className={styles.num}>{formatDuration(q.temps_total_ms)}</td>
                          <td className={styles.num}>{formatDuration(q.temps_moyen_ms)}</td>
                          <td>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => navigate('/optimiseur', { state: { sql: q.requete } })}
                              disabled={!/^\s*(select|with)\b/i.test(q.requete)}
                              title={/^\s*(select|with)\b/i.test(q.requete) ? 'Analyser avec Lumi' : 'Seules les requêtes SELECT sont analysables'}
                            >
                              Analyser
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </section>
  )
}
