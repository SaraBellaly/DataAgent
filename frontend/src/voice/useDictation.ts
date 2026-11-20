/**
 * Dictée : enregistrement au micro, détection de la fin de la prise de parole, puis transcription
 * (Whisper, via le backend). Le texte reconnu est rendu à l'appelant, qui l'affiche pour correction :
 * rien n'est envoyé automatiquement à l'agent.
 */
import { useCallback, useEffect, useRef, useState } from 'react'

import { ApiError } from '../api/client'
import { voiceApi } from '../api/endpoints'

export type DictationState = 'idle' | 'requesting' | 'recording' | 'transcribing'

const SPEECH_THRESHOLD = 0.035   // niveau RMS au-delà duquel on considère que l'utilisateur parle
const END_SILENCE_MS = 1400      // silence après la parole = fin de la phrase
const NO_SPEECH_MS = 8000        // rien entendu : on abandonne
const MAX_MS = 60_000            // une question dictée ne dépasse pas une minute

function pickMimeType(): string | undefined {
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4']
  return candidates.find((t) => typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(t))
}

export function dictationSupported(): boolean {
  return typeof window !== 'undefined' && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== 'undefined'
}

type Options = {
  onText: (text: string) => void
  onStart?: () => void
  onEnd?: () => void
}

export function useDictation({ onText, onStart, onEnd }: Options) {
  const [state, setState] = useState<DictationState>('idle')
  const [level, setLevel] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const cleanupRef = useRef<() => void>(() => undefined)
  const cancelledRef = useRef(false)
  const callbacks = useRef({ onText, onStart, onEnd })
  callbacks.current = { onText, onStart, onEnd }

  const stop = useCallback((cancel = false) => {
    cancelledRef.current = cancel
    const recorder = recorderRef.current
    if (recorder && recorder.state !== 'inactive') recorder.stop()
  }, [])

  const start = useCallback(async () => {
    if (state !== 'idle') return
    setError(null)
    setState('requesting')
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      })
    } catch (e) {
      setState('idle')
      setError(
        (e as DOMException).name === 'NotAllowedError'
          ? 'Accès au micro refusé : autorisez-le dans le navigateur pour dicter.'
          : 'Aucun micro utilisable n’a été trouvé.',
      )
      return
    }

    const mimeType = pickMimeType()
    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
    const chunks: Blob[] = []
    recorder.ondataavailable = (event) => event.data.size > 0 && chunks.push(event.data)

    // Mesure du volume pour détecter la fin de la parole et animer le bouton
    const audioContext = new AudioContext()
    const analyser = audioContext.createAnalyser()
    analyser.fftSize = 1024
    audioContext.createMediaStreamSource(stream).connect(analyser)
    const samples = new Float32Array(analyser.fftSize)
    const startedAt = performance.now()
    let lastVoice = 0
    let heard = false
    let frame = 0

    const tick = () => {
      analyser.getFloatTimeDomainData(samples)
      let sum = 0
      for (const s of samples) sum += s * s
      const rms = Math.sqrt(sum / samples.length)
      setLevel(Math.min(1, rms * 8))
      const now = performance.now()
      if (rms > SPEECH_THRESHOLD) {
        heard = true
        lastVoice = now
      }
      if (heard && now - lastVoice > END_SILENCE_MS) return stop()
      if (!heard && now - startedAt > NO_SPEECH_MS) {
        setError('Je n’ai rien entendu. Réessayez en parlant un peu plus près du micro.')
        return stop(true)
      }
      if (now - startedAt > MAX_MS) return stop()
      frame = requestAnimationFrame(tick)
    }

    let cleaned = false
    cleanupRef.current = () => {
      if (cleaned) return          // appelé à l'arrêt ET au démontage : une seule fois
      cleaned = true
      cancelAnimationFrame(frame)
      stream.getTracks().forEach((t) => t.stop())
      if (audioContext.state !== 'closed') void audioContext.close().catch(() => undefined)
      setLevel(0)
    }

    recorder.onstop = async () => {
      cleanupRef.current()
      recorderRef.current = null
      callbacks.current.onEnd?.()
      if (cancelledRef.current || chunks.length === 0) {
        setState('idle')
        return
      }
      setState('transcribing')
      try {
        const blob = new Blob(chunks, { type: recorder.mimeType || mimeType || 'audio/webm' })
        const { texte } = await voiceApi.transcribe(blob)
        if (texte.trim()) callbacks.current.onText(texte.trim())
        else setError('Je n’ai pas compris. Pouvez-vous répéter ?')
      } catch (e) {
        setError(e instanceof ApiError ? e.message : 'La transcription a échoué.')
      } finally {
        setState('idle')
      }
    }

    cancelledRef.current = false
    recorderRef.current = recorder
    recorder.start(250)
    setState('recording')
    callbacks.current.onStart?.()
    frame = requestAnimationFrame(tick)
  }, [state, stop])

  // Démontage : on coupe le micro proprement
  useEffect(() => () => {
    cancelledRef.current = true
    recorderRef.current?.state !== 'inactive' && recorderRef.current?.stop()
    cleanupRef.current()
  }, [])

  return { state, level, error, start, stop, clearError: () => setError(null) }
}
