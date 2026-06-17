import './App.css';
import { useEffect, useState, useCallback } from 'react';
import { BrowserRouter } from 'react-router-dom';
import ErrorBoundary from './components/ErrorBoundary';
import './theme.css';
import { UserProvider, useUser } from './contexts/UserContext';
import { ThemeProvider } from './contexts/ThemeContext';
import { ToastProvider } from './components/Toast';
import Layout from './components/Layout';
import Login from './components/Login';
import ChangePassword from './components/ChangePassword';
import Homepage from './components/home/Homepage';
import { purgeExpiredAttendanceDrafts } from './lib/attendanceDrafts';

function AppContent() {
  const { isAuthenticated, loading, mustChangePassword } = useUser();
  const [path, setPath] = useState(() => window.location.pathname);

  useEffect(() => {
    purgeExpiredAttendanceDrafts();
  }, []);

  // Keep our render in sync with browser navigation (back/forward).
  useEffect(() => {
    const onPop = () => setPath(window.location.pathname);
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  const navigate = useCallback((to) => {
    if (window.location.pathname !== to) window.history.pushState(null, '', to);
    setPath(to);
    window.scrollTo(0, 0);
  }, []);

  if (loading) {
    return (
      <div style={{
        minHeight: '100vh', display: 'flex', alignItems: 'center',
        justifyContent: 'center', background: 'var(--bg-primary, #111)',
      }}>
        <div className="spinner" style={{ width: 24, height: 24 }} />
      </div>
    );
  }

  // ---- Authenticated app (unchanged behavior) ----
  if (isAuthenticated) {
    if (mustChangePassword && path !== '/change-password') {
      window.history.replaceState(null, '', '/change-password');
    }
    if (path === '/change-password') return <ChangePassword />;
    return <Layout />;
  }

  // ---- Public surface ----
  // Marketing homepage lives at the root; the existing Login is reachable at
  // /login (and any other deep link still redirects to it, as before).
  if (path === '/' || path === '') {
    return <Homepage onLogin={() => navigate('/login')} />;
  }
  if (path !== '/login') {
    window.history.replaceState(null, '', '/login');
  }
  return <Login />;
}

export default function App() {
  return (
    <ErrorBoundary name="EduFlow">
      <ThemeProvider>
        <UserProvider>
          <ToastProvider>
            <BrowserRouter>
              <AppContent />
            </BrowserRouter>
          </ToastProvider>
        </UserProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}
