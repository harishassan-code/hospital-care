import '@fontsource-variable/big-shoulders-display'
import '@fontsource-variable/radio-canada'
import '@fontsource-variable/martian-mono'
import './styles/tokens.css'
import './styles/global.css'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import { hospital } from './config/hospital'

document.documentElement.style.setProperty('--sign', hospital.brandColor)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
