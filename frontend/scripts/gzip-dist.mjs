import { createGzip } from 'node:zlib'
import { createReadStream, createWriteStream } from 'node:fs'
import { readdir, stat } from 'node:fs/promises'
import { extname } from 'node:path'
import { pipeline } from 'node:stream/promises'

const distDir = new URL('../dist/', import.meta.url)
const compressibleExtensions = new Set([
  '.css',
  '.html',
  '.js',
  '.json',
  '.svg',
  '.txt',
  '.xml',
])

await gzipDirectory(distDir)

async function gzipDirectory(directoryUrl) {
  const entries = await readdir(directoryUrl, { withFileTypes: true })
  await Promise.all(
    entries.map(async (entry) => {
      const entryUrl = new URL(`${entry.name}${entry.isDirectory() ? '/' : ''}`, directoryUrl)
      if (entry.isDirectory()) {
        await gzipDirectory(entryUrl)
        return
      }
      if (!entry.isFile() || !shouldCompress(entry.name)) {
        return
      }
      const fileStats = await stat(entryUrl)
      if (fileStats.size === 0) {
        return
      }
      const sourcePath = entryUrl
      const targetPath = new URL(`${entry.name}.gz`, directoryUrl)
      await pipeline(
        createReadStream(sourcePath),
        createGzip({ level: 9 }),
        createWriteStream(targetPath),
      )
    }),
  )
}

function shouldCompress(fileName) {
  if (fileName.endsWith('.gz')) {
    return false
  }
  return compressibleExtensions.has(extname(fileName))
}
