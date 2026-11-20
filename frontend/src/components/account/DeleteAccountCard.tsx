import { Trash2 } from 'lucide-react'
import { useState } from 'react'

import { ApiError } from '../../api/client'
import { useAuth } from '../../auth/AuthContext'
import page from '../../pages/Page.module.css'
import { useVoice } from '../../voice/VoiceContext'
import { Alert } from '../ui/Alert'
import { Button } from '../ui/Button'

/** Suppression du compte (fiche, écran 4) : demande de confirmation ; annuler ne modifie rien. */
export function DeleteAccountCard() {
  const { deleteAccount } = useAuth()
  const { stop } = useVoice()
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function confirm() {
    setBusy(true)
    setError(null)
    try {
      stop()
      await deleteAccount()   // la garde des pages protégées renvoie alors à l'écran d'inscription
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'La suppression a échoué.')
      setBusy(false)
    }
  }

  return (
    <section className={`${page.card} ${page.danger}`} aria-label="Supprimer mon compte">
      <h2 className={page.cardTitle}>
        <Trash2 size={17} /> Supprimer mon compte
      </h2>
      {!confirming ? (
        <>
          <p className={page.muted}>Votre compte, vos sessions et tout votre historique seront supprimés définitivement.</p>
          <div>
            <Button variant="danger" onClick={() => setConfirming(true)}>
              Supprimer mon compte
            </Button>
          </div>
        </>
      ) : (
        <div role="alertdialog" aria-label="Confirmer la suppression du compte" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <p>
            <strong>Supprimer définitivement votre compte, vos sessions et tout votre historique ?</strong> Cette action est
            irréversible.
          </p>
          {error && <Alert tone="error">{error}</Alert>}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <Button variant="secondary" onClick={() => setConfirming(false)} disabled={busy}>
              Annuler
            </Button>
            <Button variant="danger" onClick={() => void confirm()} loading={busy}>
              Confirmer la suppression
            </Button>
          </div>
        </div>
      )}
    </section>
  )
}
