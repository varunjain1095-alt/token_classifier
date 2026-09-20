import React from 'react'

export type ChipTone = 'success' | 'warning' | 'danger' | 'info' | 'neutral'

export const Chip: React.FC<{ tone?: ChipTone; children: React.ReactNode }> = ({
  tone = 'neutral',
  children
}) => <span className={`chip chip-${tone}`}>{children}</span>

export const Card: React.FC<{
  title?: string
  children: React.ReactNode
  style?: React.CSSProperties
}> = ({ title, children, style }) => (
  <div className="card" style={style}>
    {title && <h4 style={{ margin: '0 0 14px 0' }}>{title}</h4>}
    {children}
  </div>
)

export const SectionTitle: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <h4 style={{ margin: '0 0 12px 0', fontSize: '15px', fontWeight: 700 }}>{children}</h4>
)

export const ThemeToggle: React.FC<{
  theme: 'light' | 'dark'
  onToggle: () => void
}> = ({ theme, onToggle }) => (
  <button
    className="theme-toggle"
    onClick={onToggle}
    title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
  >
    {theme === 'dark' ? '☀ Light' : '☾ Dark'}
  </button>
)
