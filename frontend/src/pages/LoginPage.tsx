import { LogIn } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Alert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { TextField } from '../components/ui/TextField'
import { AuthLayout } from '../layout/AuthLayout'
import styles from './AuthPages.module.css'

export function LoginPage() {
  const { login, notice, clearNotice } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    clearNotice()
    setLoading(true)
    try {
      await login(email.trim(), password)
      navigate('/', { replace: true })
    } catch (e) {
      // Message du serveur : unique pour un email inconnu ou un mot de passe faux, ou délai de blocage
      setError(e instanceof ApiError ? e.message : 'La connexion a échoué.')
      setPassword('')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout
      title="Bon retour"
      subtitle="Connectez-vous pour interroger la base immobilière."
      footer={
        <>
          Pas encore de compte ? <Link to="/inscription" onClick={clearNotice}>Créer un compte</Link>
        </>
      }
    >
      <form className={styles.form} onSubmit={onSubmit} noValidate>
        {notice && <Alert tone="success">{notice}</Alert>}
        {error && <Alert tone="error">{error}</Alert>}
        <TextField
          label="Adresse email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="prenom.nom@exemple.fr"
        />
        <TextField
          label="Mot de passe"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <Button type="submit" size="lg" block loading={loading} icon={<LogIn size={18} />} disabled={!email || !password}>
          Se connecter
        </Button>
        <p className={styles.note}>Session de 8 heures. Après 5 échecs, la connexion est bloquée 15 minutes.</p>
      </form>
    </AuthLayout>
  )
}
