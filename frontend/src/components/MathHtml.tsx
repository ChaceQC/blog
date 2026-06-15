import katex from 'katex'
import { useEffect, useRef } from 'react'

type MathHtmlProps = {
  className: string
  html: string
}

export function MathHtml({ className, html }: MathHtmlProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) {
      return
    }

    container.querySelectorAll<HTMLElement>('.math').forEach((node) => {
      const source = node.textContent ?? ''
      if (!source.trim()) {
        return
      }

      try {
        katex.render(source, node, {
          displayMode: node.classList.contains('block'),
          output: 'html',
          throwOnError: false,
        })
      } catch {
        node.textContent = source
      }
    })
  }, [html])

  return (
    <div
      className={className}
      dangerouslySetInnerHTML={{ __html: html }}
      ref={containerRef}
    />
  )
}
