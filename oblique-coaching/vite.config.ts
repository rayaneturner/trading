import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// URL absolue nécessaire pour l'aperçu LinkedIn (og:image).
// Sur Vercel, VERCEL_PROJECT_PRODUCTION_URL est injectée automatiquement au build.
const siteUrl = (
  process.env.SITE_URL ||
  (process.env.VERCEL_PROJECT_PRODUCTION_URL && `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`) ||
  (process.env.VERCEL_URL && `https://${process.env.VERCEL_URL}`) ||
  'https://oblique-coaching.vercel.app'
).replace(/\/$/, '')

// Maquette de prospection : non indexée tant que le client n'a pas validé (INDEXABLE=true pour la mise en ligne).
const robots = process.env.INDEXABLE === 'true' ? 'index, follow' : 'noindex, nofollow'

export default defineConfig({
  plugins: [
    react(),
    {
      name: 'site-url',
      transformIndexHtml: {
        order: 'pre',
        handler: (html) => html.replaceAll('%SITE_URL%', siteUrl).replaceAll('%ROBOTS%', robots),
      },
    },
  ],
  build: { cssCodeSplit: false },
})
