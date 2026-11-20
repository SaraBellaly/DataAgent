/** Réglages d'interface mémorisés dans le navigateur (mascotte 3D, animations). */
import { useSyncExternalStore } from 'react'

export type UiSettings = {
  mascot3d: boolean        // robote 3D (sinon : pastille animée, plus légère)
  reduceMotion: boolean    // limiter les animations, en plus du réglage du système
}

const KEY = 'reglages-interface'
const EVENT = 'reglages-interface-change'
const DEFAULTS: UiSettings = { mascot3d: true, reduceMotion: false }

let cache: UiSettings | null = null

function read(): UiSettings {
  if (cache) return cache
  try {
    const raw = localStorage.getItem(KEY)
    cache = raw ? { ...DEFAULTS, ...(JSON.parse(raw) as Partial<UiSettings>) } : DEFAULTS
  } catch {
    cache = DEFAULTS
  }
  return cache
}

export function updateUiSettings(change: Partial<UiSettings>): void {
  cache = { ...read(), ...change }
  try {
    localStorage.setItem(KEY, JSON.stringify(cache))
  } catch {
    /* réglage non mémorisé : il s'applique jusqu'au rechargement */
  }
  window.dispatchEvent(new Event(EVENT))
}

function subscribe(callback: () => void): () => void {
  window.addEventListener(EVENT, callback)
  return () => window.removeEventListener(EVENT, callback)
}

export function useUiSettings(): UiSettings {
  return useSyncExternalStore(subscribe, read, () => DEFAULTS)
}
