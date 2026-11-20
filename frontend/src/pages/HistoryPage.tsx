import { Check, MessageCircle, Pencil, Search, Trash2, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { ApiError } from '../api/client'
import { conversationsApi } from '../api/endpoints'
import type { Conversation } from '../api/types'
import { DeleteAccountCard } from '../components/account/DeleteAccountCard'
import { Alert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { Spinner } from '../components/ui/Spinner'
import { useConversations } from '../layout/ConversationsContext'
import { formatDateTime } from '../lib/format'
import styles from './HistoryPage.module.css'
import page from './Page.module.css'

/** Historique personnel : seules les conversations de l'utilisateur connecté. */
export function HistoryPage() {
  const { conversations, loading, error, refresh, remove } = useConversations()
  const [query, setQuery] = useState('')
  const [editing, setEditing] = useState<{ id: number; titre: string } | null>(null)
  const [confirmId, setConfirmId] = useState<number | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return q ? conversations.filter((c) => c.titre.toLowerCase().includes(q)) : conversations
  }, [conversations, query])

  async function rename(c: Conversation) {
    if (!editing || !editing.titre.trim()) return
    try {
      await conversationsApi.rename(c.id, editing.titre.trim())
      setEditing(null)
      await refresh()
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : 'Le renommage a échoué.')
    }
  }

  async function del(id: number) {
    try {
      await remove(id)
      setConfirmId(null)
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : 'La suppression a échoué.')
    }
  }

  return (
    <section className={page.page}>
      <div className={page.inner}>
        <header className={page.header}>
          <div className={page.headerText}>
            <h1>Historique</h1>
            <p>Vos conversations, avec leurs requêtes et les résultats déjà obtenus. Personne d’autre n’y a accès.</p>
          </div>
        </header>

        <section className={page.card}>
          <label className={styles.search}>
            <Search size={17} />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Rechercher une conversation…"
              aria-label="Rechercher une conversation"
            />
          </label>

          {(error || actionError) && <Alert tone="error">{error ?? actionError}</Alert>}
          {loading ? (
            <p className={page.muted}>
              <Spinner size={15} /> Chargement…
            </p>
          ) : filtered.length === 0 ? (
            <p className={page.muted}>
              {conversations.length === 0 ? (
                <>
                  Aucune conversation pour l’instant. <Link to="/">Poser une question</Link>
                </>
              ) : (
                'Aucune conversation ne correspond à votre recherche.'
              )}
            </p>
          ) : (
            <ul className={styles.list}>
              {filtered.map((c) => (
                <li key={c.id} className={styles.item}>
                  <span className={styles.icon} aria-hidden="true">
                    <MessageCircle size={17} />
                  </span>
                  {editing?.id === c.id ? (
                    <form
                      className={styles.renameForm}
                      onSubmit={(e) => {
                        e.preventDefault()
                        void rename(c)
                      }}
                    >
                      <input
                        autoFocus
                        value={editing.titre}
                        maxLength={120}
                        onChange={(e) => setEditing({ id: c.id, titre: e.target.value })}
                        aria-label="Nouveau titre"
                      />
                      <Button type="submit" size="sm" variant="secondary" icon={<Check size={15} />} aria-label="Enregistrer le titre" />
                      <Button type="button" size="sm" variant="ghost" icon={<X size={15} />} onClick={() => setEditing(null)} aria-label="Annuler" />
                    </form>
                  ) : (
                    <Link to={`/conversations/${c.id}`} className={styles.link}>
                      <span className={styles.title}>{c.titre}</span>
                      <span className={styles.meta}>
                        {c.nb_echanges} échange{c.nb_echanges > 1 ? 's' : ''} · {formatDateTime(c.updated_at)}
                      </span>
                    </Link>
                  )}

                  {confirmId === c.id ? (
                    <div className={styles.confirm} role="alertdialog" aria-label="Confirmer la suppression">
                      <span>Supprimer ?</span>
                      <Button size="sm" variant="ghost" onClick={() => setConfirmId(null)}>
                        Annuler
                      </Button>
                      <Button size="sm" variant="danger" onClick={() => void del(c.id)}>
                        Supprimer
                      </Button>
                    </div>
                  ) : (
                    editing?.id !== c.id && (
                      <div className={styles.actions}>
                        <Button size="sm" variant="ghost" icon={<Pencil size={15} />} onClick={() => setEditing({ id: c.id, titre: c.titre })} aria-label={`Renommer « ${c.titre} »`} />
                        <Button size="sm" variant="ghost" icon={<Trash2 size={15} />} onClick={() => setConfirmId(c.id)} aria-label={`Supprimer « ${c.titre} »`} />
                      </div>
                    )
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        <DeleteAccountCard />
      </div>
    </section>
  )
}
