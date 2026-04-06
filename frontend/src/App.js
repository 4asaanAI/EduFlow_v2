import './App.css';
import './theme.css';
import { UserProvider, useUser } from './contexts/UserContext';
import { ThemeProvider } from './contexts/ThemeContext';
import Layout from './components/Layout';
import Login from './components/Login';

function AppContent() {
  const { currentUser } = useUser();
  return currentUser ? <Layout /> : <Login />;
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
