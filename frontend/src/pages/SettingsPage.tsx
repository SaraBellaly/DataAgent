import { LogOut, MonitorSmartphone, Play, User, Volume2 } from 'lucide-react'
import { useId } from 'react'

import { useAuth } from '../auth/AuthContext'
import { DeleteAccountCard } from '../components/account/DeleteAccountCard'
import { MascotSlot } from '../components/mascot/MascotSlot'
import { Alert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { ASSISTANT_NAME } from '../layout/Sidebar'
import { formatDate } from '../lib/format'
import { updateUiSettings, useUiSettings } from '../settings/uiSettings'
import { useVoice } from '../voice/VoiceContext'
import page from './Page.module.css'
import styles from './SettingsPage.module.css'

function Switch({ label, description, checked, onChange }: { label: string; description: string; checked: boolean; onChange: (v: boolean) => void }) {
  const id = useId()
  return (
    <div className={styles.row}>
      <div className={styles.rowText}>
        <label htmlFor={id}>{label}</label>
        <p>{description}</p>
      </div>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        className={`${styles.switch} ${checked ? styles.on : ''}`}
        onClick={() => onChange(!checked)}
      >
        <span />
      </button>
    </div>
  )
}

function Slider({ label, value, min, max, step, onChange, format }: {
  label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void; format: (v: number) => string
}) {
  const id = useId()
  return (
    <div className={styles.row}>
      <div className={styles.rowText}>
        <label htmlFor={id}>{label}</label>
      </div>
      <div className={styles.slider}>
        <input id={id} type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
        <output htmlFor={id}>{format(value)}</output>
      </div>
    </div>
  )
}

export function SettingsPage() {
  const { user, logout } = useAuth()
  const voice = useVoice()
  const ui = useUiSettings()
  const voiceSelectId = useId()
  const s = voice.settings

  return (
    <section className={page.page}>
      <div className={page.inner}>
        <header className={page.header}>
          <div className={page.headerText}>
            <h1>Paramètres</h1>
            <p>Réglages enregistrés dans ce navigateur.</p>
          </div>
        </header>

        <div className={page.grid2}>
          <section className={page.card} aria-label="Voix">
            <h2 className={page.cardTitle}>
              <Volume2 size={17} /> Voix de {ASSISTANT_NAME}
            </h2>
            {!voice.supported ? (
              <Alert tone="info">Ce navigateur ne propose pas de synthèse vocale.</Alert>
            ) : (
              <>
                <Switch
                  label="Lecture automatique"
                  description="Quand vous dictez une question au micro, la réponse est lue à voix haute. Une question écrite n’est jamais lue automatiquement."
                  checked={s.enabled}
                  onChange={(enabled) => {
                    if (!enabled) voice.stop()
                    voice.updateSettings({ enabled })
                  }}
                />
                <div className={styles.row}>
                  <div className={styles.rowText}>
                    <label htmlFor={voiceSelectId}>Voix française</label>
                    <p>{voice.voices.length === 0 ? 'Aucune voix française trouvée dans ce navigateur.' : 'Les voix « Natural » d’Edge sont les plus naturelles.'}</p>
                  </div>
                  <select
                    id={voiceSelectId}
                    className={styles.select}
                    value={s.voiceURI ?? ''}
                    onChange={(e) => voice.updateSettings({ voiceURI: e.target.value || null })}
                    disabled={voice.voices.length === 0}
                  >
                    <option value="">Automatique (la meilleure)</option>
                    {voice.voices.map((v) => (
                      <option key={v.voiceURI} value={v.voiceURI}>
                        {v.name} ({v.lang})
                      </option>
                    ))}
                  </select>
                </div>
                <Slider label="Vitesse" value={s.rate} min={0.8} max={1.3} step={0.05} onChange={(rate) => voice.updateSettings({ rate })} format={(v) => `× ${v.toFixed(2)}`} />
                <Slider label="Hauteur" value={s.pitch} min={0.8} max={1.3} step={0.05} onChange={(pitch) => voice.updateSettings({ pitch })} format={(v) => v.toFixed(2)} />
                <div>
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={<Play size={15} />}
                    onClick={() =>
                      voice.speak(`Bonjour, je suis ${ASSISTANT_NAME}. Le prix moyen au m² des appartements à Bordeaux en 2025 est de 4 480 €/m².`, { force: true })
                    }
                  >
                    Écouter un exemple
                  </Button>
                </div>
              </>
            )}
          </section>

          <section className={page.card} aria-label="Interface">
            <h2 className={page.cardTitle}>
              <MonitorSmartphone size={17} /> Interface
            </h2>
            <div className={styles.preview}>
              <MascotSlot mood="welcome" size={120} />
            </div>
            <Switch
              label="Mascotte en 3D"
              description="Désactivée, la mascotte devient une pastille animée, plus légère pour les ordinateurs modestes."
              checked={ui.mascot3d}
              onChange={(mascot3d) => updateUiSettings({ mascot3d })}
            />
            <Switch
              label="Limiter les animations"
              description="La mascotte reste immobile (le réglage « animations réduites » du système est aussi respecté)."
              checked={ui.reduceMotion}
              onChange={(reduceMotion) => updateUiSettings({ reduceMotion })}
            />
          </section>
        </div>

        <section className={page.card} aria-label="Compte">
          <h2 className={page.cardTitle}>
            <User size={17} /> Compte
          </h2>
          <div className={styles.account}>
            <div>
              <p className={styles.email}>{user?.email}</p>
              <p className={page.muted}>
                Compte créé le {user ? formatDate(user.created_at) : '—'}. Seuls votre email et votre mot de passe haché (argon2id) sont conservés.
              </p>
            </div>
            <Button variant="secondary" icon={<LogOut size={16} />} onClick={() => void logout()}>
              Se déconnecter
            </Button>
          </div>
        </section>

        <DeleteAccountCard />
      </div>
    </section>
  )
}
