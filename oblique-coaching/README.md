# Oblique Coaching — maquette landing page

Maquette réalisée par ScaleSync pour Jahen Garçaut (Oblique Coaching, Bourges).

Stack : Vite + React + TypeScript + Tailwind CSS + Framer Motion (LazyMotion) + Lenis.
Le HTML est pré-rendu au build (`scripts/prerender.mjs`), ce qui donne un premier affichage rapide et une page lisible sans JavaScript.

## Commandes

```bash
npm install
npm run dev       # développement
npm run build     # build + pré-rendu → dist/
npm run preview   # sert dist/ en local
npm run og        # régénère public/og-image.png (1200×630) après une modification du visuel
```

## Déploiement Vercel

```bash
npx vercel deploy --prod
```

À lancer depuis ce dossier, ou en réglant le *Root Directory* du projet Vercel sur `oblique-coaching`.

- L'URL absolue des balises OG est déduite automatiquement de `VERCEL_PROJECT_PRODUCTION_URL`. Pour la forcer, définir `SITE_URL=https://domaine.fr`.
- La maquette est en `noindex` par défaut. Pour la mise en ligne réelle, définir `INDEXABLE=true` sur Vercel.
- Pour rafraîchir l'aperçu LinkedIn après un changement : https://www.linkedin.com/post-inspector/

## Où modifier le contenu

Tout le texte et tous les placeholders se trouvent dans `src/content.ts`.
Chaque segment `[ … ]` s'affiche automatiquement comme un placeholder en pointillés.
