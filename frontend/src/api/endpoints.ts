/** Appels aux routes réelles du backend FastAPI. */
import { api } from './client'
import type {
  AgentAnswer,
  Conversation,
  ConversationDetail,
  Dashboard,
  ExecutionResult,
  Plan,
  Transcription,
  User,
} from './types'

export const authApi = {
  register: (email: string, password: string) =>
    api<User>('/api/auth/register', { method: 'POST', json: { email, password }, authRoute: true }),
  login: (email: string, password: string) =>
    api<void>('/api/auth/login', { method: 'POST', json: { email, password }, authRoute: true }),
  logout: () => api<void>('/api/auth/logout', { method: 'POST', authRoute: true }),
  me: () => api<User>('/api/users/me', { authRoute: true }),
  deleteAccount: () => api<void>('/api/users/me', { method: 'DELETE', json: { confirmation: true } }),
}

export const agentApi = {
  ask: (question: string, conversationId?: number, signal?: AbortSignal) =>
    api<AgentAnswer>('/api/agent/questions', {
      method: 'POST',
      json: conversationId ? { question, conversation_id: conversationId } : { question },
      signal,
    }),
  execute: (historyId: number) =>
    api<ExecutionResult>(`/api/agent/questions/${historyId}/execution`, { method: 'POST' }),
  plan: (historyId: number, analyze = false) =>
    api<Plan>(`/api/agent/questions/${historyId}/plan?analyze=${analyze}`),
}

export const conversationsApi = {
  list: () => api<Conversation[]>('/api/conversations'),
  get: (id: number) => api<ConversationDetail>(`/api/conversations/${id}`),
  rename: (id: number, titre: string) =>
    api<Conversation>(`/api/conversations/${id}`, { method: 'PATCH', json: { titre } }),
  remove: (id: number) => api<void>(`/api/conversations/${id}`, { method: 'DELETE' }),
}

export const historyApi = {
  remove: (id: number) => api<void>(`/api/history/${id}`, { method: 'DELETE' }),
}

export const dashboardApi = {
  get: () => api<Dashboard>('/api/dashboard'),
}

export const voiceApi = {
  transcribe: (audio: Blob, signal?: AbortSignal) => {
    const form = new FormData()
    const extension = audio.type.includes('ogg') ? 'ogg' : audio.type.includes('mp4') ? 'mp4' : 'webm'
    form.append('audio', audio, `question.${extension}`)
    return api<Transcription>('/api/voice/transcribe', { method: 'POST', form, signal })
  },
}
