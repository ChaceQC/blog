import react from '@vitejs/plugin-react'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { defineConfig } from 'vite'

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

export default defineConfig({
  define: {
    'import.meta.env.VITE_API_BASE_URL': JSON.stringify(
      developmentConfig.apiBaseUrl,
    ),
  },
  plugins: [react()],
  preview: {
    host: developmentConfig.previewHost,
    port: developmentConfig.previewPort,
    strictPort: true,
  },
  server: {
    host: developmentConfig.devHost,
    port: developmentConfig.devPort,
    strictPort: true,
  },
})
