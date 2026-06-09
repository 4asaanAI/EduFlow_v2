import React, { createContext, useCallback, useContext, useRef, useState } from 'react';
import { CheckCircle, AlertCircle, Info, X } from 'lucide-react';

const ToastContext = createContext(null);

export function useToast() {
  return useContext(ToastContext);
}

const ICONS = {
  success: CheckCircle,
  error: AlertCircle,
  info: Info,
};

const COLORS = {
  success: '#34d399',
  error: '#f87171',
  info: '#4f8ff7',
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const idRef = useRef(0);

  const toast = useCallback((message, type = 'info', duration = 3000) => {
    const id = ++idRef.current;
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), duration);
  }, []);

  const dismiss = (id) => setToasts(prev => prev.filter(t => t.id !== id));

  const isDark = document.documentElement.getAttribute('data-theme') !== 'light';

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div style={{
        position: 'fixed', bottom: 24, right: 24, zIndex: 99999,
        display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-end',
        pointerEvents: 'none',
      }}>
        {toasts.map(t => {
          const Icon = ICONS[t.type] || ICONS.info;
          const color = COLORS[t.type] || COLORS.info;
          return (
            <div key={t.id} className="toast" style={{
              display: 'flex', alignItems: 'center', gap: 10,
              background: isDark ? '#1e1e1e' : '#ffffff',
              border: `1px solid ${isDark ? '#2e2e2e' : '#e5e5e5'}`,
              borderLeft: `3px solid ${color}`,
              borderRadius: 10, padding: '10px 14px',
              boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
              maxWidth: 340, pointerEvents: 'auto',
            }}>
              <Icon size={15} color={color} />
              <span style={{ fontSize: 13, color: isDark ? '#f5f5f5' : '#171717', flex: 1 }}>{t.message}</span>
              <button onClick={() => dismiss(t.id)} style={{ border: 'none', background: 'none', cursor: 'pointer', color: isDark ? '#888' : '#525252', display: 'flex', padding: 2 }}>
                <X size={13} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
