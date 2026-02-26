import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import {
  FolderKanban,
  ShieldCheck,
  BookOpen,
  BarChart3,
  Sun,
  Moon,
  Languages,
  Menu,
  X,
  ClipboardList,
  ShieldAlert,
  Sparkles,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { useI18n } from '../shared/i18n';

const mainNav = [
  { to: '/', labelKey: 'nav.simpleWorkflow', icon: Sparkles },
  { to: '/rulesets', labelKey: 'nav.rulesets', icon: BookOpen },
] as const;

const advancedNav = [
  { to: '/advanced', labelKey: 'nav.projects', icon: FolderKanban },
  { to: '/advanced/benchmarks', labelKey: 'nav.benchmarks', icon: BarChart3 },
  { to: '/advanced/reports/pilot-alon', labelKey: 'nav.pilotAlon', icon: ClipboardList },
  { to: '/advanced/reviews', labelKey: 'nav.reviews', icon: ShieldAlert },
] as const;

function useTheme() {
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    const saved = localStorage.getItem('archscan-theme') as 'dark' | 'light';
    if (saved) {
      document.documentElement.setAttribute('data-theme', saved);
      return saved;
    }
    document.documentElement.setAttribute('data-theme', 'light');
    return 'light';
  });

  const toggle = () => {
    setTheme(t => {
      const next = t === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('archscan-theme', next);
      return next;
    });
  };

  return { theme, toggle };
}

export default function Layout() {
  const { theme, toggle: toggleTheme } = useTheme();
  const { t, dir, toggleLocale } = useI18n();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const sidebarContent = (
    <>
      <div style={{ padding: '0 20px 24px', display: 'flex', alignItems: 'center', gap: 10 }}>
        <ShieldCheck size={24} color="var(--color-primary)" />
        <span style={{ fontSize: 18, fontWeight: 700 }}>ArchScan</span>
      </div>
      <nav style={{ display: 'flex', flexDirection: 'column', gap: 2, flex: 1 }}>
        {mainNav.map(({ to, labelKey, icon: Icon }) => (
          <NavLink key={to} to={to} end={to === '/'}
            onClick={() => setMobileOpen(false)}
            style={({ isActive }) => ({
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '10px 20px', fontSize: 14, fontWeight: 500,
              color: isActive ? 'var(--color-primary)' : 'var(--color-text-dim)',
              background: isActive ? 'rgba(108,138,255,.08)' : 'transparent',
              borderInlineStart: isActive ? '3px solid var(--color-primary)' : '3px solid transparent',
              transition: 'all 0.15s',
            })}>
            <Icon size={18} />
            {t(labelKey)}
          </NavLink>
        ))}

        {/* Advanced Mode section */}
        <button
          onClick={() => setAdvancedOpen(!advancedOpen)}
          style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '10px 20px', fontSize: 13, fontWeight: 500,
            color: 'var(--color-text-dim)', background: 'transparent',
            border: 'none', cursor: 'pointer', width: '100%',
            borderInlineStart: '3px solid transparent',
            marginTop: 8,
          }}
        >
          {advancedOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          {t('nav.advancedMode')}
        </button>

        {advancedOpen && advancedNav.map(({ to, labelKey, icon: Icon }) => (
          <NavLink key={to} to={to} end={to === '/advanced'}
            onClick={() => setMobileOpen(false)}
            style={({ isActive }) => ({
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '8px 20px 8px 36px', fontSize: 13, fontWeight: 500,
              color: isActive ? 'var(--color-primary)' : 'var(--color-text-dim)',
              background: isActive ? 'rgba(108,138,255,.08)' : 'transparent',
              borderInlineStart: isActive ? '3px solid var(--color-primary)' : '3px solid transparent',
              transition: 'all 0.15s',
            })}>
            <Icon size={16} />
            {t(labelKey)}
          </NavLink>
        ))}
      </nav>
      <div style={{ padding: '12px 20px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <button
          onClick={toggleLocale}
          className="sidebar-btn"
        >
          <Languages size={16} />
          {t('nav.language')}
        </button>
        <button
          onClick={toggleTheme}
          className="sidebar-btn"
        >
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          {theme === 'dark' ? t('nav.lightMode') : t('nav.darkMode')}
        </button>
      </div>
    </>
  );

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }} dir={dir}>
      {mobileOpen && (
        <div className="sidebar-overlay" onClick={() => setMobileOpen(false)} />
      )}

      <aside className="sidebar sidebar-desktop">
        {sidebarContent}
      </aside>

      <aside className={`sidebar sidebar-mobile ${mobileOpen ? 'sidebar-mobile-open' : ''}`}>
        <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '12px 16px 0' }}>
          <button className="sidebar-btn" style={{ width: 'auto', padding: 6 }} onClick={() => setMobileOpen(false)}>
            <X size={20} />
          </button>
        </div>
        {sidebarContent}
      </aside>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div className="mobile-header">
          <button className="sidebar-btn" style={{ width: 'auto', padding: 8 }} onClick={() => setMobileOpen(true)}>
            <Menu size={20} />
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <ShieldCheck size={20} color="var(--color-primary)" />
            <span style={{ fontWeight: 700, fontSize: 16 }}>ArchScan</span>
          </div>
          <div style={{ width: 36 }} />
        </div>
        <main style={{ flex: 1, padding: 32, overflow: 'auto' }} className="main-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
