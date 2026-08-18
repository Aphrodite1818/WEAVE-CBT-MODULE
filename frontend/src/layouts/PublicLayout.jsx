import { Brand } from '../components/Brand'

export function PublicLayout({ children, minimal = false }) {
  return (
    <main className={`public-shell ${minimal ? 'public-shell--minimal' : ''}`}>
      <header className="public-header"><Brand /><span className="public-header__tag">Secure assessment workspace</span></header>
      {children}
      <footer className="public-footer"><span>© 2026 Weave CBT</span><span>Built for focused assessment</span></footer>
    </main>
  )
}
