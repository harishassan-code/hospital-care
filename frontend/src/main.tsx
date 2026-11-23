import 'inter-ui/inter-variable-latin.css'
import '@fontsource-variable/plus-jakarta-sans'
import './styles/tokens.css'
import './styles/global.css'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import { hospital } from './config/hospital'
import { currentTheme } from './lib/theme'

document.documentElement.style.setProperty('--sign', hospital.brandColor)
document.documentElement.dataset.theme = currentTheme() // index.html does this before paint; this covers tests and old pages

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
