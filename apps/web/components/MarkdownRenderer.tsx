'use client'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
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
      // rehype-raw lets us render the <details>/<summary> collapsibles the LLM
      // emits in practice tasks. Content is self-generated, so we accept unsanitized
      // raw HTML here (same trust level as the rest of the rendered LLM markdown).
      rehypePlugins={[rehypeRaw]}
      components={{
        ...components,
        details({ children }) {
          return (
            <details className="group my-3 rounded-xl border border-line bg-sand/30 px-4 py-2 [&[open]]:bg-sand/50">
              {children}
            </details>
          )
        },
        summary({ children }) {
          return (
            <summary className="cursor-pointer select-none py-1 font-medium text-accent marker:text-accent hover:text-accentdk">
              {children}
            </summary>
          )
        },
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
