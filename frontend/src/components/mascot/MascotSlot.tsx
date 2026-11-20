import { Component, lazy, Suspense, type ReactNode } from 'react'

import type { AgentMood } from '../../chat/useConversation'
import { useUiSettings } from '../../settings/uiSettings'
import { Badge } from '../ui/Logo'
import styles from './MascotSlot.module.css'

// Three.js n'est chargé qu'au premier affichage de la mascotte (bundle initial plus léger)
const Mascot3D = lazy(() => import('./Mascot3D'))

const LABELS: Record<AgentMood, string> = {
  welcome: 'Lumi vous accueille',
  thinking: 'Lumi réfléchit',
  processing: 'Lumi prépare la requête',
  success: 'Résultat disponible',
  error: 'Une erreur est survenue',
}

function webglAvailable(): boolean {
  try {
    const canvas = document.createElement('canvas')
    return Boolean(canvas.getContext('webgl2') ?? canvas.getContext('webgl'))
  } catch {
    return false
  }
}
const HAS_WEBGL = typeof document !== 'undefined' && webglAvailable()

/** Si la 3D échoue (pilote graphique, contexte perdu…), on garde la pastille animée. */
class Fallback3D extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() {
    return { failed: true }
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children
  }
}

function BadgeMascot({ mood, size }: { mood: AgentMood; size: number }) {
  return (
    <div className={`${styles.slot} ${styles[mood]}`} style={{ width: size, height: size }}>
      <span className={styles.halo} />
      <Badge size={Math.round(size * 0.42)} />
    </div>
  )
}

type Props = {
  mood: AgentMood
  size?: number
  /** `full` : tête et buste ; `bust` : tête seule (petites tailles) */
  framing?: 'full' | 'bust'
  speaking?: boolean
}

/** Mascotte Lumi : robote 3D si le navigateur le permet, pastille animée sinon. */
export function MascotSlot({ mood, size = 120, framing, speaking = false }: Props) {
  const ui = useUiSettings()
  const fallback = <BadgeMascot mood={mood} size={size} />
  return (
    <div className={styles.frame} style={{ width: size, height: size }} role="img" aria-label={LABELS[mood]}>
      {HAS_WEBGL && ui.mascot3d ? (
        <Fallback3D fallback={fallback}>
          <Suspense fallback={fallback}>
            <Mascot3D mood={mood} speaking={speaking} framing={framing ?? (size < 90 ? 'bust' : 'full')} reduced={ui.reduceMotion} />
          </Suspense>
        </Fallback3D>
      ) : (
        fallback
      )}
    </div>
  )
}
