import { AlertCircle, CheckCircle2, Info } from 'lucide-react'
import type { ReactNode } from 'react'

import styles from './Alert.module.css'

const ICONS = { error: AlertCircle, success: CheckCircle2, info: Info }

export function Alert({ tone = 'info', children }: { tone?: 'error' | 'success' | 'info'; children: ReactNode }) {
  const Icon = ICONS[tone]
  return (
    <div className={`${styles.alert} ${styles[tone]}`} role={tone === 'error' ? 'alert' : 'status'}>
      <Icon size={18} className={styles.icon} />
      <div>{children}</div>
    </div>
  )
}
