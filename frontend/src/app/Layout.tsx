import { NavLink, Outlet } from 'react-router-dom';
import { FolderKanban, ShieldCheck, BookOpen, BarChart3 } from 'lucide-react';

const navItems = [
  { to: '/', label: 'Projects', icon: FolderKanban },
  { to: '/rulesets', label: 'Rulesets', icon: BookOpen },
  { to: '/benchmarks', label: 'Benchmarks', icon: BarChart3 },
];

export default function Layout() {
  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <aside style={{
        width: 220, background: 'var(--color-surface)', borderRight: '1px solid var(--color-border)',
        display: 'flex', flexDirection: 'column', padding: '20px 0',
      }}>
        <div style={{ padding: '0 20px 24px', display: 'flex', alignItems: 'center', gap: 10 }}>
          <ShieldCheck size={24} color="var(--color-primary)" />
          <span style={{ fontSize: 18, fontWeight: 700 }}>ArchScan</span>
        </div>
        <nav style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} end={to === '/'}
              style={({ isActive }) => ({
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '10px 20px', fontSize: 14, fontWeight: 500,
                color: isActive ? 'var(--color-primary)' : 'var(--color-text-dim)',
                background: isActive ? 'rgba(108,138,255,.08)' : 'transparent',
                borderLeft: isActive ? '3px solid var(--color-primary)' : '3px solid transparent',
                transition: 'all 0.15s',
              })}>
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main style={{ flex: 1, padding: 32, overflow: 'auto' }}>
        <Outlet />
      </main>
    </div>
  );
}
