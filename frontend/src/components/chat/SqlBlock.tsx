import { Check, Copy } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import styles from './SqlBlock.module.css'

const KEYWORDS = new Set(
  ('select from where and or not in is null as on join left right inner outer full group by order having ' +
    'limit offset distinct count sum avg min max with union all case when then else end between like ilike ' +
    'asc desc nulls first last over partition filter extract coalesce round exists cast')
    .split(' '),
)

/** Coloration légère, sans dépendance : mots-clés, chaînes, nombres, commentaires. */
function highlight(sql: string): ReactNode[] {
  const tokens = sql.match(/--[^\n]*|'(?:[^']|'')*'|\b\d+(?:\.\d+)?\b|\b[\w.]+\b|\s+|./g) ?? [sql]
  return tokens.map((token, i) => {
    if (token.startsWith('--')) return <span key={i} className={styles.comment}>{token}</span>
    if (token.startsWith("'")) return <span key={i} className={styles.string}>{token}</span>
    if (/^\d/.test(token)) return <span key={i} className={styles.number}>{token}</span>
    if (KEYWORDS.has(token.toLowerCase())) return <span key={i} className={styles.keyword}>{token}</span>
    return token
  })
}

export function SqlBlock({ sql, label = 'SQL' }: { sql: string; label?: string }) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(sql)
      setCopied(true)
      setTimeout(() => setCopied(false), 1600)
    } catch {
      /* presse-papiers refusé par le navigateur */
    }
  }

  return (
    <div className={styles.block}>
      <div className={styles.header}>
        <span>{label}</span>
        <button type="button" onClick={copy} aria-label="Copier la requête">
          {copied ? <Check size={14} /> : <Copy size={14} />}
          {copied ? 'Copié' : 'Copier'}
        </button>
      </div>
      <pre className={styles.code}>
        <code>{highlight(sql)}</code>
      </pre>
    </div>
  )
}
