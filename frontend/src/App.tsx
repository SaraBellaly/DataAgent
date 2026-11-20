import type { ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AuthProvider, useAuth } from './auth/AuthContext'
import { Spinner } from './components/ui/Spinner'
import { AppLayout } from './layout/AppLayout'
import { ChatPage } from './pages/ChatPage'
import { DashboardPage } from './pages/DashboardPage'
import { HistoryPage } from './pages/HistoryPage'
import { LoginPage } from './pages/LoginPage'
import { MascotLabPage } from './pages/MascotLabPage'
import { OptimizerPage } from './pages/OptimizerPage'
import { RegisterPage } from './pages/RegisterPage'
import { SettingsPage } from './pages/SettingsPage'
import { VoiceProvider } from './voice/VoiceContext'

function Splash() {
  return (
    <div style={{ height: '100%', display: 'grid', placeItems: 'center' }} role="status" aria-label="Chargement">
      <span style={{ color: 'var(--lav-400)' }}>
        <Spinner size={32} />
      </span>
    </div>
  )
}

/** Écrans Question, Historique… : session valide exigée (vérifiée côté serveur). */
function RequireAuth({ children }: { children: ReactNode }) {
  const { status, exitTo } = useAuth()
  if (status === 'loading') return <Splash />
  if (status === 'anonymous') return <Navigate to={exitTo} replace />
  return children
}

function PublicOnly({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  if (status === 'loading') return <Splash />
  if (status === 'authenticated') return <Navigate to="/" replace />
  return children
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/connexion" element={<PublicOnly><LoginPage /></PublicOnly>} />
          <Route path="/inscription" element={<PublicOnly><RegisterPage /></PublicOnly>} />
          <Route element={<RequireAuth><VoiceProvider><AppLayout /></VoiceProvider></RequireAuth>}>
            <Route index element={<ChatPage />} />
            {import.meta.env.DEV && <Route path="labo-mascotte" element={<MascotLabPage />} />}
            <Route path="conversations/:id" element={<ChatPage />} />
            <Route path="tableau-de-bord" element={<DashboardPage />} />
            <Route path="optimiseur" element={<OptimizerPage />} />
            <Route path="historique" element={<HistoryPage />} />
            <Route path="parametres" element={<SettingsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
