/**
 * Client HTTP de l'API FastAPI. Même origine : le cookie de session HttpOnly est envoyé
 * automatiquement par le navigateur ; le code JavaScript n'y a jamais accès.
 */

export class ApiError extends Error {
  readonly status: number
  readonly retryAfter?: number

  constructor(status: number, message: string, retryAfter?: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.retryAfter = retryAfter
  }
}

/** Émis quand la session a expiré : l'application revient à l'écran de connexion. */
export const SESSION_EXPIRED_EVENT = 'session-expired'

type Options = {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  json?: unknown
  form?: FormData
  signal?: AbortSignal
  /** Les routes d'authentification gèrent elles-mêmes le 401 (identifiants faux). */
  authRoute?: boolean
}

function messageFrom(status: number, data: unknown): string {
  const detail = (data as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  // Erreurs de validation de FastAPI (422) : liste de messages techniques en anglais
  if (Array.isArray(detail)) return 'Certaines informations saisies ne sont pas valides.'
  if (status >= 500) return 'Le serveur a rencontré une erreur. Réessayez dans un instant.'
  return 'La requête a échoué.'
}

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  const { method = 'GET', json, form, signal, authRoute = false } = options
  let response: Response
  try {
    response = await fetch(path, {
      method,
      credentials: 'same-origin',
      headers: json !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: form ?? (json !== undefined ? JSON.stringify(json) : undefined),
      signal,
    })
  } catch (error) {
    if ((error as Error).name === 'AbortError') throw error
    throw new ApiError(0, 'Le serveur est injoignable. Vérifiez que l’application est démarrée.')
  }

  if (response.status === 204) return undefined as T
  const data: unknown = await response.json().catch(() => null)

  if (!response.ok) {
    if (response.status === 401 && !authRoute) {
      window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT))
    }
    const retry = Number(response.headers.get('Retry-After'))
    throw new ApiError(response.status, messageFrom(response.status, data), Number.isFinite(retry) && retry > 0 ? retry : undefined)
  }
  return data as T
}
