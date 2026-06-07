import type { Metadata } from 'next'
import './globals.css'
import 'katex/dist/katex.min.css'
import { LocaleProvider } from '@/lib/i18n'

export const metadata: Metadata = {
  title: 'Grasp — AI mentor for developers',
  description: 'Learn System Design, algorithms, Go, Kubernetes with practice and spaced repetition.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="dark" className="h-full">
      <body className="min-h-full">
        <LocaleProvider>{children}</LocaleProvider>
      </body>
    </html>
  )
}
