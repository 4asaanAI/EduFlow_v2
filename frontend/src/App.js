import './App.css';
import { useEffect, useState } from 'react';
import { BrowserRouter } from 'react-router-dom';
import ErrorBoundary from './components/ErrorBoundary';
import './theme.css';
import { UserProvider, useUser } from './contexts/UserContext';
import { ThemeProvider } from './contexts/ThemeContext';
import { ToastProvider } from './components/Toast';
import Layout from './components/Layout';
import Login from './components/Login';
import ChangePassword from './components/ChangePassword';
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
  // The marketing homepage is now a separate project in ../homepage.
  // This app keeps auth/login and the authenticated dashboard separate.
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
