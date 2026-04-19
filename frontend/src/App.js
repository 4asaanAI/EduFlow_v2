import './App.css';
import './theme.css';
import { UserProvider, useUser } from './contexts/UserContext';
import { ThemeProvider } from './contexts/ThemeContext';
import Layout from './components/Layout';
import Login from './components/Login';

function AppContent() {
  const { isAuthenticated, loading } = useUser();

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

  return isAuthenticated ? <Layout /> : <Login />;
}

export default function App() {
  return (
    <ThemeProvider>
      <UserProvider>
        <AppContent />
      </UserProvider>
    </ThemeProvider>
  );
}
