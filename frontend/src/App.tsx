import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ToastProvider } from './shared/components/Toast';
import { I18nProvider } from './shared/i18n';
import AppRouter from './app/Router';
import { NetworkError } from './shared/api/client';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        if (error instanceof NetworkError && error.isTimeout) return failureCount < 2;
        const status = (error as { response?: { status?: number } })?.response?.status;
        if (status && status >= 400 && status < 500) return false;
        return failureCount < 1;
      },
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 8000),
    },
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
