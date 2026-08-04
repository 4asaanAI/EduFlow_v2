import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  clearAuthSession,
  clearLegacyLongLivedTokens,
  getAccessToken,
  getStoredUser,
  refreshAccessToken,
  setAuthSession,
} from '../lib/authSession';
import { API } from '../lib/api';

// NEW-08: this file used to read `REACT_APP_BACKEND_URL` itself, so it never got
// the http→https upgrade commit 80d803b added — on the login and token-refresh
// path, the two calls the whole app depends on. The address now comes from
// `lib/api.js`, which is the only place it is read.
//
// The `authFetch` wrapper that used to live here was a second copy of `apiFetch`
// with NO callers anywhere in the app. Deleted rather than kept in sync by
// discipline: there is one refreshing wrapper, `apiFetch` in `lib/api.js`. (NEW-03)

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

  // Deliberately a plain `fetch`, NOT `apiFetch`. A 401 here means the password is
  // wrong — that is the answer, not an expired session. Sending it through the
  // refreshing wrapper would try to renew a login that does not exist yet and then
  // bounce the person to the login page they are already on. Same for logout below.
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
