import { useEffect, useState } from 'react'

import styles from './ThinkingIndicator.module.css'

// L'API ne diffuse pas encore les étapes en direct : messages indicatifs, sans prétendre en être l'écho
const PHASES = ['Je lis votre question…', 'Je consulte le schéma de la base…', 'Je prépare la requête SQL…', 'Je vérifie la requête…']

/** Indicateur d'attente : points animés, phase indicative et temps écoulé. */
export function ThinkingIndicator({ name }: { name: string }) {
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    const start = Date.now()
    const timer = setInterval(() => setElapsed(Date.now() - start), 500)
    return () => clearInterval(timer)
  }, [])
  const phase = PHASES[Math.min(Math.floor(elapsed / 3500), PHASES.length - 1)]
  const seconds = Math.floor(elapsed / 1000)

  return (
    <div className={styles.thinking} role="status" aria-live="polite">
      <span className={styles.dots} aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
      <span className={styles.text}>
        <strong>{name}</strong> {phase}
      </span>
      {seconds >= 2 && <span className={styles.time}>{seconds} s</span>}
      {seconds >= 20 && <span className={styles.hint}>Le service gratuit limite le débit : la réponse peut prendre jusqu’à une minute.</span>}
    </div>
  )
}
