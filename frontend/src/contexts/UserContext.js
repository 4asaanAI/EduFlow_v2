import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  clearAuthSession,
  clearLegacyLongLivedTokens,
  getAccessToken,
  getStoredUser,
  redirectToLoginOnce,
  refreshAccessToken,
  setAuthSession,
} from '../lib/authSession';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

// ─── Authenticated fetch wrapper ────────────────────────────────────────────

export async function authFetch(url, options = {}) {
  const token = getAccessToken();
  const headers = { ...options.headers };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  let res = await fetch(url, { credentials: 'include', ...options, headers });

  if (res.status === 401) {
    try {
      await refreshAccessToken(API);
      const retryHeaders = { ...headers };
      if (getAccessToken()) retryHeaders.Authorization = `Bearer ${getAccessToken()}`;
      res = await fetch(url, { credentials: 'include', ...options, headers: retryHeaders });
      if (res.status !== 401) return res;
    } catch {}
    redirectToLoginOnce('/login');
  }

  return res;
}

// ─── Context ────────────────────────────────────────────────────────────────

const UserContext = createContext(null);

export function UserProvider({ children }) {
  const [currentUser, setCurrentUser] = useState(() => getStoredUser());
  const [token, setToken] = useState(() => getAccessToken());
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [mustChangePassword, setMustChangePassword] = useState(false);

  // Validate token on app load
  useEffect(() => {
    async function validateToken() {
      const clearedLegacy = clearLegacyLongLivedTokens();
      if (clearedLegacy) {
        setCurrentUser(null);
        setToken(null);
        setIsAuthenticated(false);
        setLoading(false);
        return;
      }
      try {
        const data = await refreshAccessToken(API);
        setCurrentUser(data.user);
        setToken(data.access_token || data.token);
        setIsAuthenticated(true);
        if (data.must_change_password) {
          setMustChangePassword(true);
          window.history.replaceState(null, '', '/change-password');
        }
      } catch {
        clearAuthSession();
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
      credentials: 'include',
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

    const nextToken = data.access_token || data.token;
    setAuthSession(nextToken, data.user);
    setToken(nextToken);
    setCurrentUser(data.user);
    setIsAuthenticated(true);
    if (data.must_change_password) {
      setMustChangePassword(true);
      window.history.replaceState(null, '', '/change-password');
    }
    return data;
  }, []);

  // ─── Logout ───────────────────────────────────────────────────────────────

  const logout = useCallback(async () => {
    try {
      await fetch(`${API}/auth/logout`, { method: 'POST', credentials: 'include' });
    } catch {}
    clearAuthSession();
    setCurrentUser(null);
    setToken(null);
    setIsAuthenticated(false);
    setMustChangePassword(false);
  }, []);

  const clearMustChangePassword = useCallback(() => {
    setMustChangePassword(false);
  }, []);


  return (
    <UserContext.Provider value={{
      currentUser,
      token,
      loading,
      isAuthenticated,
      mustChangePassword,
      loginPassword,
      logout,
      clearMustChangePassword,
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
