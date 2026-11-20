/**
 * Voix de l'assistante (texte -> parole) avec la synthèse vocale du navigateur, en français.
 * Réglages mémorisés dans le navigateur. Découplé de l'interface : les écrans n'utilisent que
 * speak / stop / speaking, et la dictée signale qu'elle commence pour couper la parole.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import { cleanForSpeech, splitSentences } from './cleanForSpeech'

export type VoiceSettings = {
  enabled: boolean      // lecture automatique des réponses
  voiceURI: string | null
  rate: number          // 0.8 à 1.3
  pitch: number         // 0.8 à 1.3
}

const DEFAULTS: VoiceSettings = { enabled: true, voiceURI: null, rate: 1.03, pitch: 1.08 }
const STORAGE_KEY = 'reglages-voix'

function loadSettings(): VoiceSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? { ...DEFAULTS, ...(JSON.parse(raw) as Partial<VoiceSettings>) } : DEFAULTS
  } catch {
    return DEFAULTS
  }
}

/** Meilleure voix française disponible : voix neuronales (Edge « Online (Natural) »), puis Google, puis les autres. */
export function rankFrenchVoices(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice[] {
  const score = (v: SpeechSynthesisVoice) =>
    (v.lang.toLowerCase() === 'fr-fr' ? 4 : 0) +
    (/natural|online|neural/i.test(v.name) ? 8 : 0) +
    (/google/i.test(v.name) ? 3 : 0) +
    (/denise|eloise|vivienne|hortense|julie|amelie|amélie|audrey|marie|celine|céline|lea|léa/i.test(v.name) ? 2 : 0)
  return voices.filter((v) => v.lang.toLowerCase().startsWith('fr')).sort((a, b) => score(b) - score(a))
}

type VoiceContextValue = {
  supported: boolean
  voices: SpeechSynthesisVoice[]
  settings: VoiceSettings
  updateSettings: (change: Partial<VoiceSettings>) => void
  speaking: boolean
  /** Lit un texte (nettoyé : sans SQL ni Markdown). force : même si la lecture automatique est coupée. */
  speak: (text: string, options?: { force?: boolean }) => void
  stop: () => void
  /** La dictée commence : l'assistante se tait et ne parle pas pendant que l'utilisateur parle. */
  setListening: (listening: boolean) => void
}

const VoiceContext = createContext<VoiceContextValue | null>(null)

export function VoiceProvider({ children }: { children: ReactNode }) {
  const supported = typeof window !== 'undefined' && 'speechSynthesis' in window
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([])
  const [settings, setSettings] = useState<VoiceSettings>(loadSettings)
  const [speaking, setSpeaking] = useState(false)
  const listeningRef = useRef(false)
  const sessionRef = useRef(0)

  useEffect(() => {
    if (!supported) return
    const load = () => setVoices(rankFrenchVoices(window.speechSynthesis.getVoices()))
    load()
    window.speechSynthesis.addEventListener('voiceschanged', load)
    return () => {
      window.speechSynthesis.removeEventListener('voiceschanged', load)
      window.speechSynthesis.cancel()
    }
  }, [supported])

  const updateSettings = useCallback((change: Partial<VoiceSettings>) => {
    setSettings((current) => {
      const next = { ...current, ...change }
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      } catch {
        /* réglage non mémorisé : sans conséquence */
      }
      return next
    })
  }, [])

  const stop = useCallback(() => {
    sessionRef.current += 1           // invalide les phrases encore en file d'attente
    if (supported) window.speechSynthesis.cancel()
    setSpeaking(false)
  }, [supported])

  const speak = useCallback(
    (text: string, options?: { force?: boolean }) => {
      if (!supported || listeningRef.current) return
      if (!settings.enabled && !options?.force) return
      const clean = cleanForSpeech(text)
      if (!clean) return
      stop()
      const session = sessionRef.current
      const voice = voices.find((v) => v.voiceURI === settings.voiceURI) ?? voices[0] ?? null
      const chunks = splitSentences(clean)
      chunks.forEach((chunk, index) => {
        const utterance = new SpeechSynthesisUtterance(chunk)
        utterance.lang = voice?.lang ?? 'fr-FR'
        if (voice) utterance.voice = voice
        utterance.rate = settings.rate
        utterance.pitch = settings.pitch
        if (index === 0) utterance.onstart = () => session === sessionRef.current && setSpeaking(true)
        if (index === chunks.length - 1) {
          utterance.onend = () => session === sessionRef.current && setSpeaking(false)
        }
        utterance.onerror = () => session === sessionRef.current && setSpeaking(false)
        window.speechSynthesis.speak(utterance)
      })
    },
    [supported, settings, voices, stop],
  )

  const setListening = useCallback(
    (listening: boolean) => {
      listeningRef.current = listening
      if (listening) stop()
    },
    [stop],
  )

  const value = useMemo(
    () => ({ supported, voices, settings, updateSettings, speaking, speak, stop, setListening }),
    [supported, voices, settings, updateSettings, speaking, speak, stop, setListening],
  )
  return <VoiceContext.Provider value={value}>{children}</VoiceContext.Provider>
}

export function useVoice(): VoiceContextValue {
  const ctx = useContext(VoiceContext)
  if (!ctx) throw new Error('useVoice doit être utilisé dans <VoiceProvider>')
  return ctx
}
