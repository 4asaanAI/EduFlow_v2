import './App.css';
import { useEffect } from 'react';
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
  const path = window.location.pathname;

  useEffect(() => {
    purgeExpiredAttendanceDrafts();
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

  if (!isAuthenticated && path !== '/login') {
    window.history.replaceState(null, '', '/login');
  }

  if (isAuthenticated && mustChangePassword && path !== '/change-password') {
    window.history.replaceState(null, '', '/change-password');
  }
  if (isAuthenticated && path === '/change-password') return <ChangePassword />;

  return isAuthenticated ? <Layout /> : <Login />;
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
