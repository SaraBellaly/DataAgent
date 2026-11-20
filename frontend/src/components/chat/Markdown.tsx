import { Fragment, type ReactNode } from 'react'

import styles from './Markdown.module.css'

/**
 * Rendu minimal et SÛR des réponses de l'agent : **gras**, `code`, listes, titres et paragraphes.
 * Aucun HTML n'est interprété (pas de dangerouslySetInnerHTML) : un texte malveillant renvoyé par le
 * modèle reste du texte.
 */
function inline(text: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) return <strong key={i}>{part.slice(2, -2)}</strong>
    if (part.startsWith('`') && part.endsWith('`') && part.length > 2) return <code key={i}>{part.slice(1, -1)}</code>
    return <Fragment key={i}>{part}</Fragment>
  })
}

type Block = { kind: 'p' | 'ul' | 'ol' | 'h' | 'pre'; lines: string[] }

function blocks(text: string): Block[] {
  const result: Block[] = []
  let fence: string[] | null = null
  for (const raw of text.replace(/\r/g, '').split('\n')) {
    const line = raw.trimEnd()
    if (line.trim().startsWith('```')) {
      if (fence) {
        result.push({ kind: 'pre', lines: fence })
        fence = null
      } else fence = []
      continue
    }
    if (fence) {
      fence.push(raw)
      continue
    }
    const trimmed = line.trim()
    if (!trimmed) {
      result.push({ kind: 'p', lines: [] })
      continue
    }
    const kind: Block['kind'] = /^[-*•]\s+/.test(trimmed)
      ? 'ul'
      : /^\d+[.)]\s+/.test(trimmed)
        ? 'ol'
        : /^#{1,4}\s+/.test(trimmed)
          ? 'h'
          : 'p'
    const content = trimmed.replace(/^[-*•]\s+|^\d+[.)]\s+|^#{1,4}\s+/, '')
    const last = result[result.length - 1]
    if (last && last.kind === kind && kind !== 'h' && last.lines.length > 0) last.lines.push(content)
    else result.push({ kind, lines: [content] })
  }
  if (fence) result.push({ kind: 'pre', lines: fence })
  return result.filter((b) => b.lines.length > 0)
}

export function Markdown({ text }: { text: string }) {
  return (
    <div className={styles.md}>
      {blocks(text).map((block, i) => {
        if (block.kind === 'ul') return <ul key={i}>{block.lines.map((l, j) => <li key={j}>{inline(l)}</li>)}</ul>
        if (block.kind === 'ol') return <ol key={i}>{block.lines.map((l, j) => <li key={j}>{inline(l)}</li>)}</ol>
        if (block.kind === 'h') return <h4 key={i}>{inline(block.lines[0])}</h4>
        if (block.kind === 'pre') return <pre key={i}>{block.lines.join('\n')}</pre>
        return <p key={i}>{block.lines.map((l, j) => <Fragment key={j}>{j > 0 && <br />}{inline(l)}</Fragment>)}</p>
      })}
    </div>
  )
}
