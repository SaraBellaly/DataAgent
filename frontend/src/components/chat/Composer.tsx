import { Code2, Mic, SendHorizontal, Square, X } from 'lucide-react'
import { useEffect, useRef, useState, type CSSProperties, type FormEvent, type KeyboardEvent } from 'react'

import { dictationSupported, useDictation } from '../../voice/useDictation'
import { useVoice } from '../../voice/VoiceContext'
import { Spinner } from '../ui/Spinner'
import styles from './Composer.module.css'

/** viaVoice : la question a été dictée au micro (la réponse sera alors lue à voix haute). */
export type ComposerSubmit = { question: string; sql?: string; viaVoice: boolean }

type Props = {
  onSubmit: (value: ComposerSubmit) => void
  disabled?: boolean
  placeholder?: string
  /** Texte imposé de l'extérieur (suggestion cliquée) */
  draft?: { text: string; withSql?: boolean; key: number }
}

const CAN_DICTATE = dictationSupported()

/** Zone de saisie : question en langage naturel, avec une requête SQL jointe en option. */
export function Composer({ onSubmit, disabled = false, placeholder, draft }: Props) {
  const [question, setQuestion] = useState('')
  const [sql, setSql] = useState('')
  const [withSql, setWithSql] = useState(false)
  const textRef = useRef<HTMLTextAreaElement>(null)
  const dictatedRef = useRef(false)
  const voice = useVoice()

  // Dictée : l'assistante se tait pendant que l'utilisateur parle ; le texte reconnu reste modifiable
  const dictation = useDictation({
    onStart: () => voice.setListening(true),
    onEnd: () => voice.setListening(false),
    onText: (text) => {
      dictatedRef.current = true
      setQuestion((current) => (current.trim() ? `${current.trim()} ${text}` : text))
      requestAnimationFrame(() => textRef.current?.focus())
    },
  })
  const recording = dictation.state === 'recording' || dictation.state === 'requesting'

  useEffect(() => {
    if (!draft) return
    setQuestion(draft.text)
    if (draft.withSql) setWithSql(true)
    textRef.current?.focus()
  }, [draft])

  // Hauteur automatique, bornée
  useEffect(() => {
    const el = textRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`
  }, [question])

  const canSend = !disabled && question.trim().length >= 3 && (!withSql || sql.trim().length > 0)

  function submit(event?: FormEvent) {
    event?.preventDefault()
    if (!canSend) return
    onSubmit({ question: question.trim(), sql: withSql ? sql.trim() : undefined, viaVoice: dictatedRef.current })
    dictatedRef.current = false
    setQuestion('')
    setSql('')
    setWithSql(false)
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <form className={`${styles.composer} ${disabled ? styles.busy : ''}`} onSubmit={submit}>
      {withSql && (
        <div className={styles.sqlBox}>
          <div className={styles.sqlHeader}>
            <span>
              <Code2 size={15} /> Requête SQL à analyser
            </span>
            <button type="button" onClick={() => setWithSql(false)} aria-label="Retirer la requête SQL">
              <X size={15} />
            </button>
          </div>
          <textarea
            className={styles.sqlInput}
            value={sql}
            onChange={(e) => setSql(e.target.value)}
            placeholder="SELECT … FROM immo.v_prix_m2_commune WHERE …"
            spellCheck={false}
            rows={4}
            maxLength={2800}
            aria-label="Requête SQL à analyser"
          />
        </div>
      )}

      <div className={styles.row}>
        <button
          type="button"
          className={`${styles.tool} ${withSql ? styles.toolActive : ''}`}
          onClick={() => setWithSql((v) => !v)}
          aria-pressed={withSql}
          title="Joindre une requête SQL existante pour analyse"
          aria-label="Joindre une requête SQL"
        >
          <Code2 size={19} />
        </button>

        <textarea
          ref={textRef}
          className={styles.input}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={placeholder ?? 'Posez votre question à votre base de données…'}
          rows={1}
          maxLength={1000}
          aria-label="Votre question"
        />

        <button
          type="button"
          className={`${styles.tool} ${recording ? styles.recording : ''}`}
          style={{ '--level': dictation.level } as CSSProperties}
          onClick={() => (recording ? dictation.stop() : void dictation.start())}
          disabled={!CAN_DICTATE || dictation.state === 'transcribing' || disabled}
          aria-label={recording ? 'Arrêter la dictée' : 'Dicter la question'}
          aria-pressed={recording}
          title={CAN_DICTATE ? (recording ? 'Arrêter' : 'Parler à l’assistante') : 'Dictée indisponible dans ce navigateur'}
        >
          {dictation.state === 'transcribing' ? <Spinner size={18} /> : recording ? <Square size={16} /> : <Mic size={19} />}
        </button>

        <button type="submit" className={styles.send} disabled={!canSend || recording} aria-label="Envoyer la question">
          <SendHorizontal size={19} />
        </button>
      </div>

      {(recording || dictation.state === 'transcribing' || dictation.error) && (
        <p className={`${styles.voiceStatus} ${dictation.error ? styles.voiceError : ''}`} role="status" aria-live="polite">
          {dictation.error ? (
            <>
              {dictation.error}
              <button type="button" onClick={dictation.clearError}>
                OK
              </button>
            </>
          ) : dictation.state === 'transcribing' ? (
            'Transcription de votre question…'
          ) : dictation.state === 'requesting' ? (
            'Autorisez l’accès au micro…'
          ) : (
            <>
              <span className={styles.meter} aria-hidden="true">
                {[0.15, 0.35, 0.6, 0.35, 0.15].map((weight, i) => (
                  <i key={i} style={{ height: `${6 + Math.min(1, dictation.level * (1 + weight * 2)) * 16}px` }} />
                ))}
              </span>
              Je vous écoute… je m’arrête quand vous vous taisez. Vous pourrez corriger le texte avant l’envoi.
            </>
          )}
        </p>
      )}
    </form>
  )
}
