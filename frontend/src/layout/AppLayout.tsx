import { Menu } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'

import { Logo } from '../components/ui/Logo'
import styles from './AppLayout.module.css'
import { ConversationsProvider } from './ConversationsContext'
import { Sidebar } from './Sidebar'

const COLLAPSE_KEY = 'sidebar-reduite'

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSE_KEY) === '1'
  } catch {
    return false
  }
}

/** Même clé pour l'accueil et une conversation : pas de remontage quand une conversation est créée. */
function chatKey(path: string): string {
  return path === '/' || path.startsWith('/conversations/') ? 'conversation' : path
}

/** Cadre de l'application : barre latérale (réductible, tiroir sur mobile) et carte principale. */
export function AppLayout() {
  const [collapsed, setCollapsed] = useState(readCollapsed)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const location = useLocation()

  useEffect(() => setDrawerOpen(false), [location.pathname])

  const toggleCollapsed = () =>
    setCollapsed((value) => {
      try {
        localStorage.setItem(COLLAPSE_KEY, value ? '0' : '1')
      } catch {
        /* préférence non mémorisée : sans conséquence */
      }
      return !value
    })

  return (
    <ConversationsProvider>
      <div className={styles.shell}>
        <div className={styles.sidebarSlot}>
          <Sidebar collapsed={collapsed} onToggleCollapsed={toggleCollapsed} />
        </div>

        <AnimatePresence>
          {drawerOpen && (
            <>
              <motion.div
                className={styles.backdrop}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                onClick={() => setDrawerOpen(false)}
              />
              <motion.div
                className={styles.drawer}
                initial={{ x: -320 }}
                animate={{ x: 0 }}
                exit={{ x: -320 }}
                transition={{ type: 'spring', stiffness: 380, damping: 36 }}
              >
                <Sidebar collapsed={false} onToggleCollapsed={toggleCollapsed} drawer onClose={() => setDrawerOpen(false)} />
              </motion.div>
            </>
          )}
        </AnimatePresence>

        <main className={styles.main}>
          <header className={styles.mobileBar}>
            <button className={styles.menuButton} onClick={() => setDrawerOpen(true)} aria-label="Ouvrir le menu">
              <Menu size={20} />
            </button>
            <Logo />
          </header>
          <AnimatePresence mode="wait">
            <motion.div
              key={chatKey(location.pathname)}
              className={styles.page}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </ConversationsProvider>
  )
}
