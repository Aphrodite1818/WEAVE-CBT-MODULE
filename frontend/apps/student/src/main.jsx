import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import '../../../src/styles/global.css'
import StudentApp from '../../../src/app/StudentApp.jsx'
import '../../../src/app/theme/branding.css'
import '../../../src/styles/product-shell.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <StudentApp />
    </BrowserRouter>
  </StrictMode>,
)
