'use client'

import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { dict as en } from './locales/en'
import { dict as ru } from './locales/ru'
import type { Dict } from './locales/en'

export type Locale = 'en' | 'ru'

const STORAGE_KEY = 'grasp_locale'

const dicts: Record<Locale, Dict> = { en, ru }

type LocaleContextValue = {
  locale: Locale
  setLocale: (l: Locale) => void
}

const LocaleContext = createContext<LocaleContextValue | null>(null)

function detectLocale(): Locale {
  if (typeof window === 'undefined') return 'en'
  const stored = localStorage.getItem(STORAGE_KEY) as Locale | null
  if (stored === 'en' || stored === 'ru') return stored
  return navigator.language.startsWith('ru') ? 'ru' : 'en'
}

export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(detectLocale)

  useEffect(() => {
    document.documentElement.lang = locale
  }, [locale])

  const setLocale = useCallback((l: Locale) => {
    localStorage.setItem(STORAGE_KEY, l)
    setLocaleState(l)
  }, [])

  return (
    <LocaleContext.Provider value={{ locale, setLocale }}>
      {children}
    </LocaleContext.Provider>
  )
}

export function useLocale() {
  const ctx = useContext(LocaleContext)
  if (!ctx) throw new Error('useLocale must be used inside LocaleProvider')
  return ctx
}

export function useT() {
  const { locale } = useLocale()
  const dict = dicts[locale]
  return useCallback(
    (key: string) => (dict as Record<string, string>)[key] ?? key,
    [dict]
  )
}

export function ruPlural(n: number, forms: [string, string, string]): string {
  const abs = Math.abs(n)
  if (abs % 10 === 1 && abs % 100 !== 11) return forms[0]
  if (abs % 10 >= 2 && abs % 10 <= 4 && (abs % 100 < 10 || abs % 100 >= 20)) return forms[1]
  return forms[2]
}
