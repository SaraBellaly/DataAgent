const numberFr = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2, useGrouping: 'always' })
const dateTimeFr = new Intl.DateTimeFormat('fr-FR', { dateStyle: 'medium', timeStyle: 'short' })
const dateFr = new Intl.DateTimeFormat('fr-FR', { dateStyle: 'medium' })

/** Séparateur de milliers : espace ordinaire (l'espace fine insécable ne s'affiche pas dans les SVG). */
export function formatNumber(value: number): string {
  return numberFr.format(value).replace(/[  ]/g, ' ')
}

/** Durée lisible : 840 ms, 2,4 s, 1 min 05 s */
export function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)} ms`
  if (ms < 60_000) return `${numberFr.format(Math.round(ms / 100) / 10)} s`
  const minutes = Math.floor(ms / 60_000)
  const seconds = Math.round((ms % 60_000) / 1000)
  return `${minutes} min ${String(seconds).padStart(2, '0')} s`
}

export function formatDateTime(iso: string): string {
  return dateTimeFr.format(new Date(iso))
}

export function formatDate(iso: string): string {
  return dateFr.format(new Date(iso))
}

/** Valeur d'une cellule de résultat : nombres à la française, null visible. */
export function formatCell(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'number') return formatNumber(value)
  if (typeof value === 'string' && /^-?\d+(\.\d+)?$/.test(value) && value.length < 16) {
    return formatNumber(Number(value))   // décimaux PostgreSQL renvoyés en texte
  }
  if (typeof value === 'boolean') return value ? 'oui' : 'non'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export function toNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && /^-?\d+(\.\d+)?$/.test(value)) return Number(value)
  return null
}
