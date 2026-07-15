import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

type Theme = 'light' | 'dark' | 'system'

interface ThemeContextType {
  theme: Theme          // 用户选择 (light/dark/system)
  resolved: 'light' | 'dark'  // 实际生效的
  setTheme: (t: Theme) => void
}

const STORAGE_KEY = 'mc-ai-bot-theme'

function getInitialTheme(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'light' || stored === 'dark' || stored === 'system') return stored
  } catch { /* localStorage unavailable */ }
  return 'system'
}

function applyTheme(resolved: 'light' | 'dark') {
  const cl = document.documentElement.classList
  if (resolved === 'dark') {
    cl.add('dark')
  } else {
    cl.remove('dark')
  }
}

const ThemeContext = createContext<ThemeContextType | null>(null)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(getInitialTheme)
  const [resolved, setResolved] = useState<'light' | 'dark'>('light')

  useEffect(() => {
    // Compute resolved theme
    const compute = (t: Theme): 'light' | 'dark' => {
      if (t === 'light') return 'light'
      if (t === 'dark') return 'dark'
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
    }

    const r = compute(theme)
    setResolved(r)
    applyTheme(r)
    localStorage.setItem(STORAGE_KEY, theme)
  }, [theme])

  // Listen to OS color scheme changes (only relevant when theme === 'system')
  useEffect(() => {
    if (theme !== 'system') return

    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = (e: MediaQueryListEvent) => {
      const r = e.matches ? 'dark' : 'light'
      setResolved(r)
      applyTheme(r)
    }

    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [theme])

  const setTheme = (t: Theme) => {
    setThemeState(t)
  }

  return (
    <ThemeContext.Provider value={{ theme, resolved, setTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme(): ThemeContextType {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider')
  return ctx
}
