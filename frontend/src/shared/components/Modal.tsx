import type { ReactNode } from 'react';
import { X } from 'lucide-react';

export default function Modal({ open, onClose, title, children }: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  if (!open) return null;
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'rgba(0,0,0,.6)', backdropFilter: 'blur(4px)',
    }} onClick={onClose}>
      <div className="card" style={{ minWidth: 480, maxWidth: 640, maxHeight: '80vh', overflow: 'auto' }}
        onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h2 style={{ fontSize: 18, fontWeight: 600 }}>{title}</h2>
          <button className="btn-secondary btn-sm" onClick={onClose}><X size={16} /></button>
        </div>
        {children}
      </div>
    </div>
  );
}
