'use client'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { useEffect, useRef, useId } from 'react'
import type { Components } from 'react-markdown'

function MermaidBlock({ code }: { code: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const uid = useId().replace(/:/g, '')

  useEffect(() => {
    let cancelled = false
    import('mermaid').then(m => {
      if (cancelled) return
      m.default.initialize({ startOnLoad: false, theme: 'dark' })
      m.default.render(`mermaid-${uid}`, code)
        .then(({ svg }) => {
          if (!cancelled && ref.current) ref.current.innerHTML = svg
        })
        .catch(console.error)
    })
    return () => { cancelled = true }
  }, [code, uid])

  return <div ref={ref} className="p-4 border border-line rounded-xl my-3 overflow-x-auto" />
}

interface MarkdownRendererProps {
  children: string
  components?: Omit<Components, 'code' | 'pre'>
}

export function MarkdownRenderer({ children, components }: MarkdownRendererProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        ...components,
        pre({ children }) {
          return <>{children}</>
        },
        code({ children, className }) {
          const lang = className?.replace('language-', '') ?? ''
          const code = String(children).replace(/\n$/, '')

          if (lang === 'mermaid') return <MermaidBlock code={code} />

          if (className) {
            return (
              <SyntaxHighlighter
                style={oneDark}
                language={lang}
                customStyle={{ borderRadius: '0.75rem', fontSize: '0.75rem', margin: '0.75rem 0' }}
              >
                {code}
              </SyntaxHighlighter>
            )
          }

          return (
            <code className="font-mono text-accent bg-accentsoft px-1 py-0.5 rounded text-xs">
              {children}
            </code>
          )
        },
      }}
    >
      {children}
    </ReactMarkdown>
  )
}
