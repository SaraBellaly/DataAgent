/** Types des réponses de l'API (miroir des schémas Pydantic de backend/app/schemas). */

export type User = {
  id: number
  email: string
  created_at: string
}

export type ExecutionResult = {
  colonnes: string[]
  lignes: unknown[][]
  nb_lignes: number
  tronque: boolean
  duree_ms: number
}

export type HistoryItem = {
  id: number
  conversation_id: number | null
  question: string
  sql_propose: string | null
  explication: string | null
  recommandations: string[]
  resultat: ExecutionResult | null
  executed_at: string | null
  created_at: string
}

export type Conversation = {
  id: number
  titre: string
  created_at: string
  updated_at: string
  nb_echanges: number
}

export type ConversationDetail = Omit<Conversation, 'nb_echanges'> & {
  echanges: HistoryItem[]
}

export type AgentAnswer = {
  history_id: number
  conversation_id: number
  question: string
  sql_propose: string | null
  explication: string
  recommandations: string[]
  etapes: string[]
  diagnostic_performance: string | null
  duree_modele_ms: number
  duree_base_ms: number
  modele: string | null
  modele_secours: boolean
}

export type Plan = {
  analyze: boolean
  plan: string
  diagnostic_performance: string | null
}

export type CostlyQuery = {
  requete: string
  appels: number
  temps_total_ms: number
  temps_moyen_ms: number
  lignes: number
}

export type Dashboard = {
  nb_conversations: number
  nb_questions: number
  nb_requetes_proposees: number
  nb_requetes_executees: number
  nb_avec_recommandations: number
  derniere_activite: string | null
  dernieres_questions: HistoryItem[]
  requetes_couteuses: CostlyQuery[]
}

export type Transcription = {
  texte: string
  duree_ms: number
}
