import { useEffect, useState } from 'react'

type BrushRect = {
  height: number
  id: string
  left: number
  rotate: number
  top: number
  width: number
}

const FORM_SELECTOR = 'input, textarea, select, [contenteditable="true"]'
const BRUSH_ROOT_SELECTOR = '.public-shell, .post-prose, .content-preview'
const BRUSH_EXCLUDE_SELECTOR = [
  '.sr-only',
  '[aria-hidden="true"]',
  '.brand-mark',
  '.icon-button',
  'input',
  'textarea',
  'select',
  '[contenteditable="true"]',
].join(',')

function isFormSelection() {
  const activeElement = document.activeElement
  return activeElement instanceof HTMLElement && activeElement.closest(FORM_SELECTOR)
}

function isBrushableTextNode(node: Node) {
  if (!node.textContent?.trim() || !(node.parentElement instanceof HTMLElement)) {
    return false
  }

  if (node.parentElement.closest(BRUSH_EXCLUDE_SELECTOR)) {
    return false
  }

  return Boolean(node.parentElement.closest(BRUSH_ROOT_SELECTOR))
}

function doesRangeIntersectNode(range: Range, node: Node) {
  try {
    return range.intersectsNode(node)
  } catch {
    return false
  }
}

function getTextNodesInRange(range: Range) {
  const root = range.commonAncestorContainer
  if (root.nodeType === Node.TEXT_NODE) {
    return isBrushableTextNode(root) ? [root as Text] : []
  }

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
  const textNodes: Text[] = []
  let node = walker.nextNode()
  while (node) {
    if (isBrushableTextNode(node) && doesRangeIntersectNode(range, node)) {
      textNodes.push(node as Text)
    }
    node = walker.nextNode()
  }

  return textNodes
}

function getSelectionRects() {
  const selection = window.getSelection()
  if (!selection || selection.isCollapsed || selection.rangeCount === 0 || isFormSelection()) {
    return []
  }

  const range = selection.getRangeAt(0)
  const selectedText = selection.toString().trim()
  if (!selectedText) {
    return []
  }

  return getTextNodesInRange(range)
    .flatMap((textNode) => {
      const textRange = document.createRange()
      const startOffset = range.startContainer === textNode ? range.startOffset : 0
      const endOffset = range.endContainer === textNode ? range.endOffset : textNode.length
      textRange.setStart(textNode, startOffset)
      textRange.setEnd(textNode, endOffset)
      return Array.from(textRange.getClientRects())
    })
    .filter((rect) => rect.width > 2 && rect.height > 2)
    .slice(0, 40)
    .map((rect, index) => ({
      height: Math.ceil(rect.height),
      id: `selection-line-${index}`,
      left: Math.round(rect.left),
      rotate: index % 2 === 0 ? -0.35 : 0.28,
      top: Math.round(rect.top),
      width: Math.ceil(rect.width),
    }))
}

function areRectsEqual(currentRects: BrushRect[], nextRects: BrushRect[]) {
  return (
    currentRects.length === nextRects.length &&
    currentRects.every((currentRect, index) => {
      const nextRect = nextRects[index]
      return (
        currentRect.height === nextRect.height &&
        currentRect.left === nextRect.left &&
        currentRect.top === nextRect.top &&
        currentRect.width === nextRect.width
      )
    })
  )
}

export function SelectionHighlight() {
  const [rects, setRects] = useState<BrushRect[]>([])

  useEffect(() => {
    let frame = 0
    const update = () => {
      window.cancelAnimationFrame(frame)
      frame = window.requestAnimationFrame(() => {
        const nextRects = getSelectionRects()
        setRects((currentRects) =>
          areRectsEqual(currentRects, nextRects) ? currentRects : nextRects,
        )
      })
    }

    document.documentElement.classList.add('selection-brush-enabled')
    document.addEventListener('selectionchange', update)
    document.addEventListener('scroll', update, true)
    window.addEventListener('resize', update)
    window.addEventListener('keyup', update)
    window.addEventListener('pointerup', update)
    window.addEventListener('touchend', update)
    window.addEventListener('touchcancel', update)
    window.visualViewport?.addEventListener('scroll', update)
    window.visualViewport?.addEventListener('resize', update)

    update()

    return () => {
      window.cancelAnimationFrame(frame)
      document.documentElement.classList.remove('selection-brush-enabled')
      document.removeEventListener('selectionchange', update)
      document.removeEventListener('scroll', update, true)
      window.removeEventListener('resize', update)
      window.removeEventListener('keyup', update)
      window.removeEventListener('pointerup', update)
      window.removeEventListener('touchend', update)
      window.removeEventListener('touchcancel', update)
      window.visualViewport?.removeEventListener('scroll', update)
      window.visualViewport?.removeEventListener('resize', update)
    }
  }, [])

  if (rects.length === 0) {
    return null
  }

  return (
    <div className="selection-brush-layer" aria-hidden="true">
      {rects.map((rect) => (
        <span
          className="selection-brush-stroke"
          key={rect.id}
          style={{
            height: `${rect.height + 7}px`,
            transform: `translate3d(${rect.left - 4}px, ${rect.top - 2}px, 0) rotate(${rect.rotate}deg) skewX(-4deg)`,
            width: `${rect.width + 8}px`,
          }}
        >
          <span className="selection-brush-stroke__ink" />
        </span>
      ))}
    </div>
  )
}
