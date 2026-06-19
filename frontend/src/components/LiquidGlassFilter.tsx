import { type RefObject, useEffect, useState } from 'react'

const NEUTRAL_DISPLACEMENT_MAP = `data:image/svg+xml;utf8,${encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2"><rect width="2" height="2" fill="rgb(128,128,128)"/></svg>',
)}`

type LiquidGlassFilterProps = {
  targetRef: RefObject<HTMLElement | null>
  lensId: string
  edgeId: string
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}

function smoothstep(edge0: number, edge1: number, value: number) {
  const progress = clamp((value - edge0) / (edge1 - edge0), 0, 1)
  return progress * progress * (3 - 2 * progress)
}

function roundedRectSdf(
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number,
) {
  const halfWidth = width / 2 - radius - 1
  const halfHeight = height / 2 - radius - 1
  const qx = Math.abs(x) - halfWidth
  const qy = Math.abs(y) - halfHeight
  const outside = Math.hypot(Math.max(qx, 0), Math.max(qy, 0))
  const inside = Math.min(Math.max(qx, qy), 0)

  return outside + inside - radius
}

function createRoundedRectDisplacementMap(width: number, height: number) {
  const mapWidth = clamp(Math.round(width), 96, 720)
  const mapHeight = clamp(Math.round(height), 48, 180)
  const canvas = document.createElement('canvas')
  canvas.width = mapWidth
  canvas.height = mapHeight

  const context = canvas.getContext('2d', { willReadFrequently: false })
  if (!context) {
    return NEUTRAL_DISPLACEMENT_MAP
  }

  const image = context.createImageData(mapWidth, mapHeight)
  const pixels = image.data
  const radius = clamp(mapHeight * 0.36, 18, 28)
  const edgeWidth = clamp(mapHeight * 0.38, 18, 36)
  const halfWidth = mapWidth / 2
  const halfHeight = mapHeight / 2

  for (let y = 0; y < mapHeight; y += 1) {
    for (let x = 0; x < mapWidth; x += 1) {
      const px = x + 0.5 - halfWidth
      const py = y + 0.5 - halfHeight
      const distance = roundedRectSdf(px, py, mapWidth, mapHeight, radius)
      const edge = 1 - smoothstep(0, edgeWidth, Math.abs(distance))
      const innerLip = 1 - smoothstep(0, edgeWidth * 0.72, Math.max(-distance, 0))
      const outerNormalX =
        roundedRectSdf(px + 1, py, mapWidth, mapHeight, radius) -
        roundedRectSdf(px - 1, py, mapWidth, mapHeight, radius)
      const outerNormalY =
        roundedRectSdf(px, py + 1, mapWidth, mapHeight, radius) -
        roundedRectSdf(px, py - 1, mapWidth, mapHeight, radius)
      const normalLength = Math.hypot(outerNormalX, outerNormalY) || 1
      const normalX = outerNormalX / normalLength
      const normalY = outerNormalY / normalLength
      const cornerFactor = Math.min(
        1,
        (Math.abs(px) / halfWidth) ** 5 + (Math.abs(py) / halfHeight) ** 5,
      )
      const prism = Math.sin(edge * Math.PI) * innerLip
      const bend = edge * (76 + cornerFactor * 34) + prism * 18
      const horizontalBend = normalX * bend * 0.9
      const verticalBend = normalY * bend * 1.08
      const index = (y * mapWidth + x) * 4

      pixels[index] = clamp(128 + horizontalBend, 0, 255)
      pixels[index + 1] = clamp(128 + verticalBend, 0, 255)
      pixels[index + 2] = clamp(128 + prism * 36 - cornerFactor * edge * 18, 0, 255)
      pixels[index + 3] = 255
    }
  }

  context.putImageData(image, 0, 0)
  return canvas.toDataURL('image/png')
}

export function LiquidGlassFilter({
  targetRef,
  lensId,
  edgeId,
}: LiquidGlassFilterProps) {
  const [mapHref, setMapHref] = useState(NEUTRAL_DISPLACEMENT_MAP)

  useEffect(() => {
    const element = targetRef.current
    if (!element || typeof ResizeObserver === 'undefined') {
      return
    }

    let lastSize = ''
    let frameId = 0

    const updateMap = () => {
      cancelAnimationFrame(frameId)
      frameId = requestAnimationFrame(() => {
        const rect = element.getBoundingClientRect()
        const width = Math.round(rect.width)
        const height = Math.round(rect.height)
        const sizeKey = `${width}x${height}`

        if (width < 2 || height < 2 || sizeKey === lastSize) {
          return
        }

        lastSize = sizeKey
        setMapHref(createRoundedRectDisplacementMap(width, height))
      })
    }

    updateMap()

    const observer = new ResizeObserver(updateMap)
    observer.observe(element)
    window.addEventListener('resize', updateMap)

    return () => {
      cancelAnimationFrame(frameId)
      observer.disconnect()
      window.removeEventListener('resize', updateMap)
    }
  }, [targetRef])

  return (
    <svg className="glass-filter-defs" aria-hidden="true" focusable="false">
      <filter
        id={lensId}
        x="-10%"
        y="-80%"
        width="120%"
        height="260%"
        colorInterpolationFilters="sRGB"
      >
        <feImage
          href={mapHref}
          x="0"
          y="0"
          width="100%"
          height="100%"
          preserveAspectRatio="none"
          result="glassDisplacementMap"
        />
        <feDisplacementMap
          in="SourceGraphic"
          in2="glassDisplacementMap"
          scale="26"
          xChannelSelector="R"
          yChannelSelector="G"
        />
      </filter>
      <filter
        id={edgeId}
        x="-14%"
        y="-90%"
        width="128%"
        height="280%"
        colorInterpolationFilters="sRGB"
      >
        <feImage
          href={mapHref}
          x="0"
          y="0"
          width="100%"
          height="100%"
          preserveAspectRatio="none"
          result="glassEdgeMap"
        />
        <feDisplacementMap
          in="SourceGraphic"
          in2="glassEdgeMap"
          scale="54"
          xChannelSelector="R"
          yChannelSelector="G"
        />
      </filter>
    </svg>
  )
}
