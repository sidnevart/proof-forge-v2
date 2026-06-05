'use client'

import { useLocale, type Locale } from '@/lib/i18n'

export function LocaleToggle({ className = '' }: { className?: string }) {
  const { locale, setLocale } = useLocale()

  return (
    <div className={`inline-flex items-center rounded-full border border-line px-1.5 py-0.5 text-[11px] font-mono ${className}`}>
      <button
        onClick={() => setLocale('en')}
        className={`px-1 py-0.5 rounded transition-colors uppercase ${
          locale === 'en' ? 'text-accent font-semibold' : 'text-mute hover:text-ink'
        }`}
      >
        EN
      </button>
      <span className="text-line/80 select-none mx-0.5">|</span>
      <button
        onClick={() => setLocale('ru')}
        className={`px-1 py-0.5 rounded transition-colors uppercase ${
          locale === 'ru' ? 'text-accent font-semibold' : 'text-mute hover:text-ink'
        }`}
      >
        RU
      </button>
    </div>
  )
}
