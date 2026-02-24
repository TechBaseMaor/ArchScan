import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import en from './locales/en.json';
import he from './locales/he.json';

export type Locale = 'en' | 'he';

const catalogs: Record<Locale, Record<string, string>> = { en, he };

interface I18nContextValue {
  locale: Locale;
  setLocale: (l: Locale) => void;
  toggleLocale: () => void;
  t: (key: string, params?: Record<string, string | number>) => string;
  dir: 'ltr' | 'rtl';
  formatDate: (d: string | Date) => string;
  formatDateTime: (d: string | Date) => string;
  formatNumber: (n: number) => string;
}

const I18nContext = createContext<I18nContextValue | undefined>(undefined);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => {
    return (localStorage.getItem('archscan-language') as Locale) || 'en';
  });

  const dir = locale === 'he' ? 'rtl' : 'ltr';

  useEffect(() => {
    localStorage.setItem('archscan-language', locale);
    document.documentElement.lang = locale;
    document.documentElement.dir = dir;
  }, [locale, dir]);

  const setLocale = useCallback((l: Locale) => setLocaleState(l), []);
  const toggleLocale = useCallback(() => setLocaleState(p => p === 'en' ? 'he' : 'en'), []);

  const t = useCallback((key: string, params?: Record<string, string | number>): string => {
    let text = catalogs[locale]?.[key] ?? catalogs.en[key] ?? key;
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        text = text.replace(`{${k}}`, String(v));
      });
    }
    return text;
  }, [locale]);

  const formatDate = useCallback((d: string | Date) => {
    return new Date(d).toLocaleDateString(locale === 'he' ? 'he-IL' : 'en-US');
  }, [locale]);

  const formatDateTime = useCallback((d: string | Date) => {
    return new Date(d).toLocaleString(locale === 'he' ? 'he-IL' : 'en-US');
  }, [locale]);

  const formatNumber = useCallback((n: number) => {
    return n.toLocaleString(locale === 'he' ? 'he-IL' : 'en-US');
  }, [locale]);

  return (
    <I18nContext.Provider value={{ locale, setLocale, toggleLocale, t, dir, formatDate, formatDateTime, formatNumber }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n must be used within I18nProvider');
  return ctx;
}
