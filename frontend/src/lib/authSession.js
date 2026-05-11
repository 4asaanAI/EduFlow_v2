const TOKEN_KEY = 'eduflow_token';
const USER_KEY = 'eduflow_user';

let accessToken = null;
let authUser = null;
let refreshPromise = null;

export function getAccessToken() {
  return accessToken;
}

export function getAuthUser() {
  return authUser;
}

export function getAuthHeaders(contentType = 'application/json') {
  const headers = contentType ? { 'Content-Type': contentType } : {};
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  return headers;
}

export function setAuthSession(token, user) {
  accessToken = token || null;
  authUser = user || null;
  try {
    if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
    else localStorage.removeItem(USER_KEY);
  } catch {}
}

export function clearAuthSession() {
  accessToken = null;
  authUser = null;
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem('token');
  } catch {}
}

export function getStoredUser() {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function parseJwt(token) {
  try {
    const [, payload] = token.split('.');
    return JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')));
  } catch {
    return null;
  }
}

export function clearLegacyLongLivedTokens() {
  let legacy = null;
  try {
    legacy = localStorage.getItem(TOKEN_KEY) || localStorage.getItem('token');
  } catch {}
  if (!legacy) return false;

  const payload = parseJwt(legacy);
  const expiresAtMs = payload?.exp ? payload.exp * 1000 : 0;
  const moreThanOneHourLeft = expiresAtMs - Date.now() > 60 * 60 * 1000;
  clearAuthSession();
  return moreThanOneHourLeft;
}

export async function refreshAccessToken(apiBaseUrl) {
  if (refreshPromise) return refreshPromise;
  refreshPromise = fetch(`${apiBaseUrl}/auth/refresh`, {
    method: 'POST',
    credentials: 'include',
  })
    .then(async (res) => {
      if (!res.ok) throw new Error('Refresh failed');
      const data = await res.json();
      setAuthSession(data.access_token || data.token, data.user);
      return data;
    })
    .finally(() => {
      refreshPromise = null;
    });
  return refreshPromise;
}
