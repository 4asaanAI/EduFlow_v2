import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const TOKEN_KEY = 'eduflow_token';
const USER_KEY = 'eduflow_user';

// ─── Token helpers ──────────────────────────────────────────────────────────

function getStoredToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || null;
  } catch {
    return null;
  }
}

function getStoredUser() {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function storeAuth(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

// ─── Authenticated fetch wrapper ────────────────────────────────────────────

export async function authFetch(url, options = {}) {
  const token = getStoredToken();
  const headers = { ...options.headers };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(url, { ...options, headers });

  if (res.status === 401) {
    clearAuth();
    if (window.location.pathname !== '/login') {
      window.location.href = '/login';
    }
  }

  return res;
}

// ─── Context ────────────────────────────────────────────────────────────────

const UserContext = createContext(null);

export function UserProvider({ children }) {
  const [currentUser, setCurrentUser] = useState(() => getStoredUser());
  const [token, setToken] = useState(() => getStoredToken());
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  // Validate token on app load
  useEffect(() => {
    async function validateToken() {
      const storedToken = getStoredToken();
      if (!storedToken) {
        setLoading(false);
        setIsAuthenticated(false);
        return;
      }

      try {
        const res = await fetch(`${API}/auth/me`, {
          headers: { Authorization: `Bearer ${storedToken}` },
        });
        if (res.ok) {
          const data = await res.json();
          setCurrentUser(data.user);
          setToken(storedToken);
          setIsAuthenticated(true);
          localStorage.setItem(USER_KEY, JSON.stringify(data.user));
        } else {
          clearAuth();
          setCurrentUser(null);
          setToken(null);
          setIsAuthenticated(false);
        }
      } catch {
        // Network error — clear auth, require re-login
        clearAuth();
        setCurrentUser(null);
        setToken(null);
        setIsAuthenticated(false);
      }
      setLoading(false);
    }

    validateToken();
  }, []);

  // ─── Password login ──────────────────────────────────────────────────────

  const loginPassword = useCallback(async (username, password) => {
    const res = await fetch(`${API}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });

    let data = {};
    try {
      data = await res.json();
    } catch {
      throw new Error(res.ok ? 'Unexpected server response' : 'Invalid username or password');
    }

    if (!res.ok) throw new Error(data.detail || 'Login failed');

    storeAuth(data.token, data.user);
    setToken(data.token);
    setCurrentUser(data.user);
    setIsAuthenticated(true);
    return data;
  }, []);

  // ─── Logout ───────────────────────────────────────────────────────────────

  const logout = useCallback(() => {
    clearAuth();
    setCurrentUser(null);
    setToken(null);
    setIsAuthenticated(false);
  }, []);

  return (
    <UserContext.Provider value={{
      currentUser,
      token,
      loading,
      isAuthenticated,
      loginPassword,
      logout,
    }}>
      {children}
    </UserContext.Provider>
  );
}

export function useUser() {
  const ctx = useContext(UserContext);
  if (!ctx) throw new Error('useUser must be used within UserProvider');
  return ctx;
}
