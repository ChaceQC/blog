const SITE_NAV_MAX_TAGS = 8

export function siteNavTagLabels(
  tagsJson: Record<string, unknown> | null | undefined,
): string[] {
  if (!tagsJson) {
    return []
  }
  const rawItems = Array.isArray(tagsJson.items)
    ? tagsJson.items
    : Array.isArray(tagsJson.tags)
      ? tagsJson.tags
      : []
  return normalizeTagLabels(rawItems)
}

export function siteNavTagsToText(
  tagsJson: Record<string, unknown> | null | undefined,
): string {
  return siteNavTagLabels(tagsJson).join('，')
}

export function siteNavTagsPayload(
  tagsText: string,
): Record<string, string[]> | null {
  const items = normalizeTagLabels(tagsText.split(/[,，、\n]/))
  return items.length > 0 ? { items } : null
}

function normalizeTagLabels(items: unknown[]): string[] {
  const tags: string[] = []
  const seen = new Set<string>()
  for (const item of items) {
    if (typeof item !== 'string') {
      continue
    }
    const tag = item.trim()
    if (tag === '') {
      continue
    }
    const tagKey = tag.toLocaleLowerCase()
    if (seen.has(tagKey)) {
      continue
    }
    tags.push(tag)
    seen.add(tagKey)
    if (tags.length >= SITE_NAV_MAX_TAGS) {
      break
    }
  }
  return tags
}
