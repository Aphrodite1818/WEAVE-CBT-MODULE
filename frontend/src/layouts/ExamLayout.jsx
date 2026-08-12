import { Brand } from '../components/Brand'
import { Icon } from '../lib/icons'

export function ExamLayout({ title, time, children }) {
  return <main className="exam-shell"><header className="exam-header"><Brand /><div className="exam-header__title"><small>Currently taking</small><strong>{title}</strong></div><div className="timer"><Icon name="clock" /><span><small>Time remaining</small><strong>{time}</strong></span></div></header>{children}</main>
}
