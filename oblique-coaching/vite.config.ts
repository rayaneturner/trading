import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// URL absolue nécessaire pour l'aperçu LinkedIn (og:image).
// Injectée automatiquement au build : URL sur Netlify, VERCEL_PROJECT_PRODUCTION_URL sur Vercel.
const siteUrl = (
  process.env.SITE_URL ||
  (process.env.NETLIFY && process.env.URL) ||
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
