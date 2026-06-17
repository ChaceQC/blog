const apiTimestampZonePattern = /(?:Z|[+-]\d{2}:?\d{2})$/i

const chinaDateFormatter = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  timeZone: 'Asia/Shanghai',
})

const chinaDateTimeFormatter = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
  timeZone: 'Asia/Shanghai',
})

export function parseApiDate(value: string): Date {
  return new Date(normalizeApiTimestamp(value))
}

export function parseApiTime(value: string): number {
  return parseApiDate(value).getTime()
}

export function formatChinaDate(value: string | null, fallback: string): string {
  if (!value) {
    return fallback
  }

  const date = parseApiDate(value)
  if (Number.isNaN(date.getTime())) {
    return fallback
  }

  return chinaDateFormatter.format(date).replaceAll('/', '-')
}

export function formatChinaDateTime(
  value: string | null,
  fallback: string,
): string {
  if (!value) {
    return fallback
  }

  const date = parseApiDate(value)
  if (Number.isNaN(date.getTime())) {
    return fallback
  }

  return chinaDateTimeFormatter.format(date).replaceAll('/', '-')
}

export function localDateTimeInputFromApi(value: string | null): string | null {
  if (!value) {
    return null
  }

  const date = parseApiDate(value)
  if (Number.isNaN(date.getTime())) {
    return null
  }

  const parts = new Intl.DateTimeFormat('en-CA', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: 'Asia/Shanghai',
  }).formatToParts(date)
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]))
  return `${values.year}-${values.month}-${values.day}T${values.hour}:${values.minute}`
}

export function apiTimestampFromChinaDateTimeInput(value: string): string | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value)
  if (!match) {
    return null
  }

  const [, year, month, day, hour, minute] = match
  const timestamp = Date.UTC(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour) - 8,
    Number(minute),
  )
  return Number.isNaN(timestamp) ? null : new Date(timestamp).toISOString()
}

function normalizeApiTimestamp(value: string): string {
  return apiTimestampZonePattern.test(value) ? value : `${value}Z`
}
