export const encoder = new TextEncoder()
export const decoder = new TextDecoder()

export function base64urlDecode(value: string): ArrayBuffer {
  const base64 = value.replace(/-/g, '+').replace(/_/g, '/')
  const padded = `${base64}${'='.repeat((4 - (base64.length % 4)) % 4)}`
  const binary = atob(padded)
  return toArrayBuffer(Uint8Array.from(binary, (char) => char.charCodeAt(0)))
}

export function base64urlEncode(value: Uint8Array): string {
  const binary = Array.from(value, (byte) => String.fromCharCode(byte)).join('')
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '')
}

export function textBytes(value: string): ArrayBuffer {
  return toArrayBuffer(encoder.encode(value))
}

export function toArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  const buffer = new ArrayBuffer(bytes.byteLength)
  new Uint8Array(buffer).set(bytes)
  return buffer
}

export function concatBytes(...items: Uint8Array[]): Uint8Array {
  const totalLength = items.reduce((total, item) => total + item.byteLength, 0)
  const output = new Uint8Array(totalLength)
  let offset = 0
  for (const item of items) {
    output.set(item, offset)
    offset += item.byteLength
  }
  return output
}

export function uint32be(value: number): Uint8Array {
  return new Uint8Array([
    (value >>> 24) & 0xff,
    (value >>> 16) & 0xff,
    (value >>> 8) & 0xff,
    value & 0xff,
  ])
}

export function toError(error: unknown, fallbackMessage: string): Error {
  return error instanceof Error ? error : new Error(fallbackMessage)
}

export function sleep(milliseconds: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, milliseconds)
  })
}
