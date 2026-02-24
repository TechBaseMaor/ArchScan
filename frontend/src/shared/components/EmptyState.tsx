import type { ReactNode } from 'react';

export default function EmptyState({ icon, message, action }: {
  icon: ReactNode;
  message: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      {icon}
      <p>{message}</p>
      {action}
    </div>
  );
}
