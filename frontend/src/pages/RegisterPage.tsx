import { UserPlus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { Alert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { TextField } from '../components/ui/TextField'
import { AuthLayout } from '../layout/AuthLayout'
import styles from './AuthPages.module.css'

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function RegisterPage() {
  const { register, notice } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [touched, setTouched] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const emailError = touched && !EMAIL.test(email.trim()) ? 'Adresse email invalide.' : null
  const passwordError = touched && password.length < 8 ? 'Au moins 8 caractères.' : null

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setTouched(true)
    setError(null)
    if (!EMAIL.test(email.trim()) || password.length < 8) return
    setLoading(true)
    try {
      await register(email.trim(), password)
      navigate('/connexion', { replace: true })   // fiche, écran 1 : redirection vers la connexion
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'L’inscription a échoué.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthLayout
      title="Créer un compte"
      subtitle="Seuls votre email et votre mot de passe sont demandés."
      footer={
        <>
          Déjà un compte ? <Link to="/connexion">Se connecter</Link>
        </>
      }
    >
      <form className={styles.form} onSubmit={onSubmit} noValidate>
        {notice && !error && <Alert tone="success">{notice}</Alert>}
        {error && <Alert tone="error">{error}</Alert>}
        <TextField
          label="Adresse email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={emailError}
          placeholder="prenom.nom@exemple.fr"
        />
        <TextField
          label="Mot de passe"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          maxLength={128}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={passwordError}
          hint="8 caractères minimum. Il est stocké haché (argon2id), jamais en clair."
        />
        <Button type="submit" size="lg" block loading={loading} icon={<UserPlus size={18} />}>
          Créer mon compte
        </Button>
      </form>
    </AuthLayout>
  )
}
