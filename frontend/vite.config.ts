/// <reference types="vitest" />

import react from '@vitejs/plugin-react'
import JavaScriptObfuscator from 'javascript-obfuscator'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { defineConfig } from 'vite'
import type { PluginOption } from 'vite'

type DevelopmentConfig = {
  devHost: string
  devPort: number
  previewHost: string
  previewPort: number
  apiBaseUrl: string
}

const developmentConfig = JSON.parse(
  readFileSync(resolve('config/development.json'), 'utf-8'),
) as DevelopmentConfig
const developmentApiUrl = new URL(developmentConfig.apiBaseUrl)
const developmentApiTarget = `${developmentApiUrl.protocol}//${developmentApiUrl.host}`
const developmentApiPath = developmentApiUrl.pathname.replace(/\/$/, '') || '/api'

export default defineConfig(({ command }) => ({
  define:
    command === 'serve'
      ? {
          'import.meta.env.VITE_API_BASE_URL': JSON.stringify('/api'),
        }
      : {},
  plugins: [
    react(),
    command === 'build' ? obfuscateBuildChunks() : undefined,
  ],
  preview: {
    host: developmentConfig.previewHost,
    port: developmentConfig.previewPort,
    strictPort: true,
  },
  server: {
    host: developmentConfig.devHost,
    port: developmentConfig.devPort,
    proxy: {
      '/api': {
        target: developmentApiTarget,
        changeOrigin: true,
        rewrite: (path) =>
          developmentApiPath === '/api'
            ? path
            : path.replace(/^\/api(?=\/|$)/, developmentApiPath),
      },
    },
    strictPort: true,
  },
  test: {
    environment: 'jsdom',
  },
}))

function obfuscateBuildChunks(): PluginOption {
  return {
    name: 'blog-obfuscate-build-chunks',
    generateBundle(_, bundle) {
      for (const item of Object.values(bundle)) {
        if (item.type !== 'chunk' || !item.fileName.endsWith('.js')) {
          continue
        }
        item.code = JavaScriptObfuscator.obfuscate(item.code, {
          compact: true,
          controlFlowFlattening: true,
          controlFlowFlatteningThreshold: 0.35,
          deadCodeInjection: true,
          deadCodeInjectionThreshold: 0.1,
          identifierNamesGenerator: 'hexadecimal',
          numbersToExpressions: true,
          rotateStringArray: true,
          selfDefending: true,
          simplify: true,
          splitStrings: true,
          splitStringsChunkLength: 8,
          stringArray: true,
          stringArrayThreshold: 0.75,
          transformObjectKeys: true,
        }).getObfuscatedCode()
      }
    },
  }
}
