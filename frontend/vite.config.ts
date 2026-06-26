/// <reference types="vitest" />

import react from '@vitejs/plugin-react'
import JavaScriptObfuscator from 'javascript-obfuscator'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { defineConfig } from 'vite'
import type { OutputChunk } from 'rolldown'
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
  build: {
    chunkSizeWarningLimit: 900,
    rolldownOptions: {
      output: {
        assetFileNames: 'assets/[hash][extname]',
        chunkFileNames: 'assets/[hash].js',
        entryFileNames: 'assets/[hash].js',
        codeSplitting: {
          groups: [
            {
              name: 'vendor-react',
              test: /node_modules[\\/](react|react-dom|scheduler|react-router|react-router-dom)[\\/]/,
              priority: 80,
              maxSize: 420 * 1024,
            },
            {
              name: 'vendor-query',
              test: /node_modules[\\/]@tanstack[\\/]react-query[\\/]/,
              priority: 70,
              maxSize: 320 * 1024,
            },
            {
              name: 'vendor-katex',
              test: /node_modules[\\/]katex[\\/]/,
              priority: 70,
              maxSize: 320 * 1024,
            },
            {
              name: 'vendor-icons',
              test: /node_modules[\\/]lucide-react[\\/]/,
              priority: 65,
              maxSize: 260 * 1024,
            },
            {
              name: 'vendor-ui',
              test: /node_modules[\\/]@yohaku[\\/]/,
              priority: 65,
              maxSize: 260 * 1024,
            },
            {
              name: 'app-encryption',
              test: /src[\\/]api[\\/](encryption|client|config)\.ts$/,
              priority: 60,
              maxSize: 240 * 1024,
            },
            {
              name: 'app-encryption-salt',
              test: /src[\\/]api[\\/]encryptionSaltSocket\.ts$/,
              priority: 62,
              maxSize: 120 * 1024,
            },
            {
              name: 'app-encryption-envelope',
              test: /src[\\/]api[\\/]encryptionEnvelope\.ts$/,
              priority: 62,
              maxSize: 120 * 1024,
            },
            {
              name: 'app-encryption-esid',
              test: /src[\\/]api[\\/](encryptionEsid|encryptionWasm)\.ts$/,
              priority: 62,
              maxSize: 120 * 1024,
            },
            {
              name: 'app-public',
              test: /src[\\/](routes[\\/]public|features[\\/](posts|sites|seo))[\\/]/,
              priority: 45,
              maxSize: 300 * 1024,
            },
            {
              name: 'vendor',
              test: /node_modules[\\/]/,
              priority: 10,
              maxSize: 360 * 1024,
            },
          ],
        },
      },
    },
  },
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
        ws: true,
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
        if (
          item.type !== 'chunk' ||
          !item.fileName.endsWith('.js') ||
          !shouldObfuscateChunk(item)
        ) {
          continue
        }
        item.code = JavaScriptObfuscator.obfuscate(item.code, {
          compact: true,
          controlFlowFlattening: true,
          controlFlowFlatteningThreshold: 0.75,
          debugProtection: true,
          debugProtectionInterval: 4_000,
          deadCodeInjection: true,
          deadCodeInjectionThreshold: 0.18,
          disableConsoleOutput: true,
          identifierNamesGenerator: 'hexadecimal',
          numbersToExpressions: true,
          rotateStringArray: true,
          selfDefending: true,
          shuffleStringArray: true,
          simplify: true,
          splitStrings: true,
          splitStringsChunkLength: 4,
          stringArray: true,
          stringArrayCallsTransform: true,
          stringArrayCallsTransformThreshold: 0.5,
          stringArrayEncoding: ['base64'],
          stringArrayIndexesType: ['hexadecimal-number'],
          stringArrayThreshold: 0.75,
          stringArrayWrappersChainedCalls: true,
          stringArrayWrappersCount: 4,
          stringArrayWrappersParametersMaxCount: 4,
          stringArrayWrappersType: 'function',
          transformObjectKeys: true,
        }).getObfuscatedCode()
      }
    },
  }
}

function shouldObfuscateChunk(chunk: OutputChunk): boolean {
  return Object.keys(chunk.modules).some(isProjectSourceModule)
}

function isProjectSourceModule(moduleId: string): boolean {
  const normalized = moduleId.replace(/\\/g, '/')
  return normalized.includes('/src/') && !normalized.includes('/node_modules/')
}
