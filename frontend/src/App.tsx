import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ToastProvider } from './shared/components/Toast';
import AppRouter from './app/Router';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AppRouter />
      </ToastProvider>
    </QueryClientProvider>
  );
}
