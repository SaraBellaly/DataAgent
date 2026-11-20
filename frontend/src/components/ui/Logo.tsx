import styles from './Logo.module.css'

/** Pastille ronde à initiale, dégradé rose-lavande : avatar de l'assistante (« L ») ou monogramme (« AI »). */
export function Badge({ label = 'L', size = 28 }: { label?: string; size?: number }) {
  return (
    <span
      className={styles.badge}
      style={{ width: size, height: size, fontSize: Math.round(size * (label.length > 1 ? 0.38 : 0.46)) }}
      aria-hidden="true"
    >
      {label}
    </span>
  )
}

/** stacked : nom sur deux lignes (barre latérale) ; compact : monogramme seul (barre réduite). */
export function Logo({ compact = false, stacked = false }: { compact?: boolean; stacked?: boolean }) {
  if (compact) return <Badge label="AI" size={34} />
  return stacked ? (
    <span className={styles.stacked}>
      <span>AI Database</span>
      <span className="gradient-text">Engineer</span>
    </span>
  ) : (
    <span className={styles.name}>
      AI Database <span className="gradient-text">Engineer</span>
    </span>
  )
}
