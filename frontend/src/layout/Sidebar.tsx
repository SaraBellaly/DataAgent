import {
  Gauge,
  History,
  LayoutGrid,
  LogOut,
  MessageCircle,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Settings,
  X,
} from 'lucide-react'
import type { ComponentType } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'
import { Badge, Logo } from '../components/ui/Logo'
import { useConversations } from './ConversationsContext'
import styles from './Sidebar.module.css'

type NavItem = { to: string; label: string; icon: ComponentType<{ size?: number }>; tint: string; end?: boolean }

const NAV: NavItem[] = [
  { to: '/', label: 'Conversation', icon: MessageCircle, tint: 'lavender', end: true },
  { to: '/tableau-de-bord', label: 'Tableau de bord', icon: LayoutGrid, tint: 'rose' },
  { to: '/optimiseur', label: 'SQL Optimizer', icon: Gauge, tint: 'peach' },
  { to: '/historique', label: 'Historique', icon: History, tint: 'sky' },
  { to: '/parametres', label: 'Paramètres', icon: Settings, tint: 'mint' },
]

export const ASSISTANT_NAME = 'Lumi'

type Props = {
  collapsed: boolean
  onToggleCollapsed: () => void
  /** Mode tiroir (petits écrans) */
  drawer?: boolean
  onClose?: () => void
}

export function Sidebar({ collapsed, onToggleCollapsed, drawer = false, onClose }: Props) {
  const { user, logout } = useAuth()
  const { conversations, loading } = useConversations()
  const navigate = useNavigate()
  const compact = collapsed && !drawer
  const initial = (user?.email ?? '?').charAt(0).toUpperCase()

  const close = () => onClose?.()

  return (
    <aside className={`${styles.sidebar} ${compact ? styles.collapsed : ''}`} aria-label="Navigation principale">
      <div className={styles.top}>
        <Logo compact={compact} stacked />
        {drawer ? (
          <button className={styles.iconButton} onClick={close} aria-label="Fermer le menu">
            <X size={18} />
          </button>
        ) : (
          <button
            className={styles.iconButton}
            onClick={onToggleCollapsed}
            aria-label={collapsed ? 'Déplier la barre latérale' : 'Réduire la barre latérale'}
            title={collapsed ? 'Déplier' : 'Réduire'}
          >
            {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
          </button>
        )}
      </div>

      <button
        className={styles.newChat}
        onClick={() => {
          navigate('/', { state: { reset: Date.now() } })
          close()
        }}
        title="Nouvelle conversation"
      >
        <span className={styles.newChatIcon}>
          <Plus size={18} />
        </span>
        {!compact && <span>Nouvelle conversation</span>}
      </button>

      <nav className={styles.nav}>
        {NAV.map(({ to, label, icon: Icon, tint, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={close}
            title={compact ? label : undefined}
            className={({ isActive }) => `${styles.navItem} ${isActive ? styles.active : ''}`}
          >
            <span className={`${styles.navIcon} ${styles[tint]}`}>
              <Icon size={18} />
            </span>
            {!compact && <span className={styles.navLabel}>{label}</span>}
          </NavLink>
        ))}
      </nav>

      {!compact && (
        <section className={styles.recents} aria-label="Conversations récentes">
          <h2 className={styles.recentsTitle}>Récents</h2>
          {loading ? (
            <p className={styles.muted}>Chargement…</p>
          ) : conversations.length === 0 ? (
            <p className={styles.muted}>Aucune conversation pour l’instant.</p>
          ) : (
            <ul>
              {conversations.slice(0, 8).map((c) => (
                <li key={c.id}>
                  <NavLink
                    to={`/conversations/${c.id}`}
                    onClick={close}
                    className={({ isActive }) => `${styles.recent} ${isActive ? styles.recentActive : ''}`}
                    title={c.titre}
                  >
                    {c.titre}
                  </NavLink>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <div className={styles.bottom}>
        <div className={styles.assistant} title={`${ASSISTANT_NAME}, votre assistante base de données`}>
          <span className={styles.assistantIcon}>
            <Badge size={30} />
            <span className={styles.online} aria-hidden="true" />
          </span>
          {!compact && (
            <span className={styles.assistantText}>
              <strong>{ASSISTANT_NAME}</strong>
              <small>Assistante base de données</small>
            </span>
          )}
        </div>

        <div className={styles.profile}>
          <span className={styles.avatar} aria-hidden="true">
            {initial}
          </span>
          {!compact && <span className={styles.email} title={user?.email}>{user?.email}</span>}
          <button className={styles.iconButton} onClick={() => void logout()} aria-label="Se déconnecter" title="Se déconnecter">
            <LogOut size={18} />
          </button>
        </div>
      </div>
    </aside>
  )
}
