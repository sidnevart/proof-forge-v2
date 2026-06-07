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
        // Default heading/text rhythm for the conspect (Theory tab). Callers that pass
        // their own `components` (e.g. the compact chat bubble) override these below.
        h2({ children }) {
          const text = typeof children === 'string' ? children : String(children ?? '')
          const id = text.toLowerCase().replace(/[^\wа-яё]/gi, '-').replace(/-+/g, '-').replace(/^-|-$/g, '')
          return <h2 id={id} className="font-display text-lg font-bold text-ink mt-8 mb-3 pb-2 border-b border-line/60 scroll-mt-4">{children}</h2>
        },
        h3({ children }) {
          const text = typeof children === 'string' ? children : String(children ?? '')
          const id = text.toLowerCase().replace(/[^\wа-яё]/gi, '-').replace(/-+/g, '-').replace(/^-|-$/g, '')
          return <h3 id={id} className="font-semibold text-ink mt-6 mb-2 scroll-mt-4">{children}</h3>
        },
        p({ children }) {
          return <p className="text-ink/90 leading-relaxed mb-3 last:mb-0">{children}</p>
        },
        hr() {
          return <hr className="my-6 border-line/40" />
        },
        ul({ children }) {
          return <ul className="list-disc list-inside space-y-1 mb-3 text-ink/90">{children}</ul>
        },
        ol({ children }) {
          return <ol className="list-decimal list-inside space-y-1 mb-3 text-ink/90">{children}</ol>
        },
        li({ children }) {
          return <li className="pl-1">{children}</li>
        },
        // GFM tables — react-markdown emits bare <table> with no styling, so columns
        // collide. Wrap in a horizontally-scrollable container with bordered, padded cells.
        // `table-auto` + `min-w-full` lets columns size to content and the container scroll
        // on narrow screens instead of cells squishing/overlapping ("drift").
        table({ children }) {
          return (
            <div className="my-4 overflow-x-auto rounded-xl border border-line">
              <table className="min-w-full table-auto border-collapse text-sm">{children}</table>
            </div>
          )
        },
        thead({ children }) {
          return <thead className="bg-sand/40">{children}</thead>
        },
        tr({ children }) {
          return <tr className="border-b border-line/60 last:border-0">{children}</tr>
        },
        th({ children }) {
          return <th className="px-3 py-2 text-left align-top font-semibold text-ink border-r border-line/40 last:border-0 whitespace-normal break-words">{children}</th>
        },
        td({ children }) {
          return <td className="px-3 py-2 align-top text-ink/90 border-r border-line/40 last:border-0 whitespace-normal break-words [overflow-wrap:anywhere]">{children}</td>
        },
        blockquote({ children }) {
          return <blockquote className="border-l-2 border-accent/50 pl-4 my-3 text-ink/80 italic">{children}</blockquote>
        },
        // Caller overrides win for the keys above.
        ...components,
        // code/pre/details/summary are always ours (code/pre excluded from caller type).
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

          // Treat as a block when the fence carried a language OR the content spans
          // multiple lines. Without this, language-less multi-line fences (common from
          // the LLM) fall through to the inline pill and render as wrapped garbage.
          const isBlock = !!className || code.includes('\n')
          if (isBlock) {
            return (
              <SyntaxHighlighter
                style={oneDark}
                language={lang || 'text'}
                customStyle={{
                  borderRadius: '0.75rem',
                  fontSize: '0.8125rem',
                  lineHeight: '1.5',
                  margin: '0.75rem 0',
                  maxWidth: '100%',
                  overflowX: 'auto',
                }}
              >
                {code}
              </SyntaxHighlighter>
            )
          }

          return (
            <code className="font-mono text-accent bg-accentsoft px-1 py-0.5 rounded text-[0.85em] break-words">
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
