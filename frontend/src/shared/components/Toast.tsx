import { useState, useCallback, createContext, useContext, type ReactNode } from 'react';

interface Toast {
  id: number;
  message: string;
  type: 'error' | 'success';
}

interface ToastContextValue {
  showError: (msg: string) => void;
  showSuccess: (msg: string) => void;
}

const ToastContext = createContext<ToastContextValue>({
  showError: () => {},
  showSuccess: () => {},
});

export function useToast() {
  return useContext(ToastContext);
}

let nextId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const add = useCallback((message: string, type: 'error' | 'success') => {
    const id = ++nextId;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4000);
  }, []);

  const showError = useCallback((msg: string) => add(msg, 'error'), [add]);
  const showSuccess = useCallback((msg: string) => add(msg, 'success'), [add]);

  return (
    <ToastContext.Provider value={{ showError, showSuccess }}>
      {children}
      <div className="toast-container">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.type}`}>
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
