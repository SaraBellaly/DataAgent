export function Spinner({ size = 18, label }: { size?: number; label?: string }) {
  return (
    <span role={label ? 'status' : undefined} style={{ display: 'inline-flex' }}>
      <svg width={size} height={size} viewBox="0 0 24 24" style={{ animation: 'spin 0.9s linear infinite' }} aria-hidden="true">
        <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeOpacity="0.2" strokeWidth="3" />
        <path d="M21 12a9 9 0 0 0-9-9" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
      </svg>
      {label && <span className="visually-hidden">{label}</span>}
    </span>
  )
}
