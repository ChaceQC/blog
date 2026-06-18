export function safePreviewHref(value: string): string {
  const url = value.trim()
  if (url === '') {
    return '#'
  }
  if (url.startsWith('/') && !url.startsWith('//')) {
    return url
  }

  try {
    const parsed = new URL(url)
    if (['http:', 'https:', 'mailto:'].includes(parsed.protocol)) {
      return url
    }
  } catch {
    return '#'
  }
  return '#'
}
