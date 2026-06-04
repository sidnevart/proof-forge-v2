import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Grasp — AI-ментор для разработчиков',
  description: 'Изучай System Design, алгоритмы, Go, Kubernetes с практикой и spaced repetition.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" data-theme="dark" className="h-full">
      <body className="min-h-full">{children}</body>
    </html>
  )
}
