import { MascotSlot } from '../components/mascot/MascotSlot'
import type { AgentMood } from '../chat/useConversation'

const MOODS: AgentMood[] = ['welcome', 'thinking', 'processing', 'success', 'error']

/** Banc d'essai de la mascotte (développement uniquement, absent du build de production). */
export function MascotLabPage() {
  return (
    <div style={{ padding: 24, display: 'flex', flexWrap: 'wrap', gap: 16, overflowY: 'auto' }}>
      <figure style={{ margin: 0, textAlign: 'center' }}>
        <MascotSlot mood="welcome" size={460} />
        <figcaption style={{ fontSize: 13, color: 'var(--text-muted)' }}>grand format</figcaption>
      </figure>
      {MOODS.map((mood) => (
        <figure key={mood} style={{ margin: 0, textAlign: 'center' }}>
          <MascotSlot mood={mood} size={230} />
          <figcaption style={{ fontSize: 13, color: 'var(--text-muted)' }}>{mood}</figcaption>
        </figure>
      ))}
      <figure style={{ margin: 0, textAlign: 'center' }}>
        <MascotSlot mood="welcome" size={230} speaking />
        <figcaption style={{ fontSize: 13, color: 'var(--text-muted)' }}>speaking</figcaption>
      </figure>
      <figure style={{ margin: 0, textAlign: 'center' }}>
        <MascotSlot mood="success" size={56} />
        <figcaption style={{ fontSize: 13, color: 'var(--text-muted)' }}>bust 56 px</figcaption>
      </figure>
    </div>
  )
}
