import { StrictMode } from 'react'
import { createRoot, hydrateRoot } from 'react-dom/client'
import App from './App'
import './index.css'

const root = document.getElementById('root')!
const app = (
  <StrictMode>
    <App />
  </StrictMode>
)

// HTML pré-rendu au build → hydratation ; sinon (dev) rendu client classique
if (root.firstElementChild) hydrateRoot(root, app)
else createRoot(root).render(app)
