const deniedPublicSitePaths = ['/admin', '/api/admin']

function isPublicSitePath(value: string): boolean {
  let path = value.split(/[?#]/, 1)[0].toLowerCase()
  let decodedPath = path
  try {
    for (let i = 0; i < 3; i += 1) {
      decodedPath = decodeURIComponent(path).toLowerCase()
      if (decodedPath === path) {
        break
      }
      path = decodedPath
    }
  } catch {
    return false
  }
  if (decodedPath.includes('\\') || decodedPath.startsWith('//')) {
    return false
  }
  return deniedPublicSitePaths.every(
    (prefix) => decodedPath !== prefix && !decodedPath.startsWith(`${prefix}/`),
  )
}

export function safePreviewHref(value: string): string {
  const url = value.trim()
  if (url === '') {
    return '#'
  }
  if (url.startsWith('/') && !url.startsWith('//')) {
    return isPublicSitePath(url) ? url : '#'
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
