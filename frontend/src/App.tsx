import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ToastProvider } from './shared/components/Toast';
import { I18nProvider } from './shared/i18n';
import AppRouter from './app/Router';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <I18nProvider>
        <ToastProvider>
          <AppRouter />
        </ToastProvider>
      </I18nProvider>
    </QueryClientProvider>
  );
}
