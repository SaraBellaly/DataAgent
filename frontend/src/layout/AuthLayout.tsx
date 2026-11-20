import type { ReactNode } from 'react'

import { MascotSlot } from '../components/mascot/MascotSlot'
import { Logo } from '../components/ui/Logo'
import styles from './AuthLayout.module.css'

/** Écrans d'inscription et de connexion : une carte blanche centrée sur le fond pastel. */
export function AuthLayout({ title, subtitle, children, footer }: {
  title: string
  subtitle: string
  children: ReactNode
  footer: ReactNode
}) {
  return (
    <main className={styles.page}>
      <section className={styles.card}>
        <div className={styles.top}>
          <Logo />
          <div className={styles.mascot}>
            <MascotSlot mood="welcome" size={118} />
          </div>
        </div>
        <header className={styles.header}>
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </header>
        {children}
        <footer className={styles.footer}>{footer}</footer>
      </section>
      <p className={styles.legal}>
        Données : DVF 2025 (Etalab) et INSEE, Licence Ouverte 2.0. Seuls votre email et un mot de passe haché sont conservés.
      </p>
    </main>
  )
}
