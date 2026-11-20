import { BarChart3, Table2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import type { ExecutionResult } from '../../api/types'
import { formatCell, formatDuration, formatNumber, toNumber } from '../../lib/format'
import styles from './ResultView.module.css'

// Colonnes à traiter comme des étiquettes même si elles contiennent des chiffres
const LABEL_LIKE = /(^|_)(code|id|insee|annee|année|year|dep|departement|reg|arr)(_|$)|^code|code_/i

function analyse(result: ExecutionResult) {
  const { colonnes, lignes } = result
  const measures = colonnes
    .map((name, index) => ({ name, index }))
    .filter(({ name, index }) => {
      if (LABEL_LIKE.test(name)) return false
      const values = lignes.map((r) => r[index]).filter((v) => v !== null && v !== undefined)
      return values.length > 0 && values.every((v) => toNumber(v) !== null)
    })
  const measureIdx = new Set(measures.map((m) => m.index))
  const labels = colonnes.map((name, index) => ({ name, index })).filter(({ index }) => !measureIdx.has(index))
  // Un nom lisible plutôt qu'un code : nom/libellé d'abord, puis toute colonne qui n'est pas un code
  const label =
    labels.find(({ name }) => /(^|_)(nom|libelle|ville|type|mois|nature)/i.test(name)) ??
    labels.find(({ name }) => !LABEL_LIKE.test(name)) ??
    labels[0] ??
    null
  return { measures, label }
}

function prettyName(column: string): string {
  return column.replace(/_/g, ' ').replace(/\bm2\b/i, 'm²')
}

export function ResultView({ result }: { result: ExecutionResult }) {
  const { measures, label } = useMemo(() => analyse(result), [result])
  const chartable = label !== null && measures.length > 0 && result.lignes.length >= 2 && result.lignes.length <= 50
  const [view, setView] = useState<'table' | 'chart'>(chartable ? 'chart' : 'table')
  const measure = measures[0]

  const data = useMemo(
    () =>
      chartable && label && measure
        ? result.lignes.map((row) => ({ label: String(row[label.index] ?? '—'), value: toNumber(row[measure.index]) ?? 0 }))
        : [],
    [chartable, label, measure, result.lignes],
  )

  if (result.lignes.length === 0) {
    return <p className={styles.empty}>La requête n’a renvoyé aucune ligne.</p>
  }

  // Une seule ligne : les valeurs numériques en grand (ex. prix moyen au m²)
  if (result.lignes.length === 1 && measures.length > 0 && measures.length <= 4) {
    const row = result.lignes[0]
    const context = result.colonnes
      .map((c, i) => ({ c, i }))
      .filter(({ i }) => !measures.some((m) => m.index === i))
      .map(({ c, i }) => `${prettyName(c)} : ${formatCell(row[i])}`)
    return (
      <div className={styles.kpiWrap}>
        {context.length > 0 && <p className={styles.kpiContext}>{context.join(' · ')}</p>}
        <div className={styles.kpis}>
          {measures.map((m) => (
            <div key={m.name} className={styles.kpi}>
              <span className={styles.kpiValue}>{formatCell(row[m.index])}</span>
              <span className={styles.kpiLabel}>{prettyName(m.name)}</span>
            </div>
          ))}
        </div>
        <Meta result={result} />
      </div>
    )
  }

  return (
    <div className={styles.wrap}>
      {chartable && (
        <div className={styles.switch} role="tablist" aria-label="Affichage du résultat">
          <button role="tab" aria-selected={view === 'chart'} className={view === 'chart' ? styles.on : ''} onClick={() => setView('chart')}>
            <BarChart3 size={15} /> Graphique
          </button>
          <button role="tab" aria-selected={view === 'table'} className={view === 'table' ? styles.on : ''} onClick={() => setView('table')}>
            <Table2 size={15} /> Tableau
          </button>
        </div>
      )}

      {view === 'chart' && chartable && measure ? (
        <div className={styles.chart} style={{ height: Math.min(56 + data.length * 34, 520) }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} layout="vertical" margin={{ top: 4, right: 24, bottom: 4, left: 8 }}>
              <defs>
                <linearGradient id="bar-gradient" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0" stopColor="#f2b3ca" />
                  <stop offset="1" stopColor="#b9a3ee" />
                </linearGradient>
              </defs>
              <CartesianGrid horizontal={false} stroke="#efeaf4" />
              <XAxis type="number" tickFormatter={(v: number) => formatNumber(v)} tick={{ fill: '#8a8398', fontSize: 12 }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="label" width={170} tick={{ fill: '#5b5468', fontSize: 12 }} axisLine={false} tickLine={false} />
              <Tooltip
                cursor={{ fill: 'rgba(221, 210, 248, 0.25)' }}
                formatter={(v) => [formatNumber(Number(v)), prettyName(measure.name)]}
                contentStyle={{ borderRadius: 12, border: '1px solid #ece7f1', boxShadow: '0 8px 24px rgba(110,80,150,.12)' }}
              />
              <Bar dataKey="value" fill="url(#bar-gradient)" radius={[0, 4, 4, 0]} barSize={18} animationDuration={600} />
            </BarChart>
          </ResponsiveContainer>
          <p className={styles.chartCaption}>
            {prettyName(measure.name)} par {prettyName(label?.name ?? '')}
          </p>
        </div>
      ) : (
        <div className={styles.tableScroll}>
          <table className={styles.table}>
            <thead>
              <tr>
                {result.colonnes.map((c, i) => (
                  <th key={c} className={measures.some((m) => m.index === i) ? styles.num : ''}>
                    {prettyName(c)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.lignes.map((row, r) => (
                <tr key={r}>
                  {row.map((cell, i) => (
                    <td key={i} className={measures.some((m) => m.index === i) ? styles.num : ''}>
                      {formatCell(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Meta result={result} />
    </div>
  )
}

function Meta({ result }: { result: ExecutionResult }) {
  return (
    <p className={styles.meta}>
      {result.nb_lignes} ligne{result.nb_lignes > 1 ? 's' : ''}
      {result.tronque && ' (affichage limité aux 200 premières)'} · exécutée en {formatDuration(result.duree_ms)} · lecture seule
    </p>
  )
}
