import katex from 'katex'
import { useLayoutEffect, useRef } from 'react'

import { API_BASE_URL } from '../api/config.ts'

type MathHtmlProps = {
  className: string
  html: string
}

export function MathHtml({ className, html }: MathHtmlProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useLayoutEffect(() => {
    const container = containerRef.current
    if (!container) {
      return
    }
    container.innerHTML = html

    container
      .querySelectorAll<HTMLImageElement>('img[src^="/api/"], img[src^="api/"]')
      .forEach((node) => {
        node.src = apiResourceUrl(node.getAttribute('src') ?? '')
      })

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
      ref={containerRef}
    />
  )
}

function apiResourceUrl(path: string): string {
  const apiBase = API_BASE_URL.replace(/\/$/, '')
  if (path.startsWith('/api/')) {
    return `${apiBase}${path.slice('/api'.length)}`
  }
  if (path.startsWith('api/')) {
    return `${apiBase}/${path.slice('api/'.length)}`
  }
  return path
}
