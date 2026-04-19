const BACKEND = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND}/api`;

const TOKEN_KEY = 'eduflow_token';

/**
 * Build headers for API requests.
 * Uses JWT token from localStorage exclusively.
 */
function getHeaders() {
  const headers = {
    'Content-Type': 'application/json',
  };

  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  return headers;
}

/**
 * Wrapper around fetch that handles 401 responses by clearing auth and redirecting.
 */
async function apiFetch(url, options = {}) {
  const res = await fetch(url, options);

  if (res.status === 401) {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem('eduflow_user');
    window.location.href = '/';
    return res;
  }

  return res;
}

// --- Chat ---
export async function getConversations() {
  const res = await apiFetch(`${API}/chat/conversations`, { headers: getHeaders() });
  return res.json();
}

export async function createConversation() {
  const res = await apiFetch(`${API}/chat/conversations`, {
    method: 'POST', headers: getHeaders(), body: JSON.stringify({}),
  });
  return res.json();
}

export async function updateConversation(convId, update) {
  const res = await apiFetch(`${API}/chat/conversations/${convId}`, {
    method: 'PATCH', headers: getHeaders(), body: JSON.stringify(update),
  });
  return res.json();
}

export async function deleteConversation(convId) {
  const res = await apiFetch(`${API}/chat/conversations/${convId}`, {
    method: 'DELETE', headers: getHeaders(),
  });
  return res.json();
}

export async function getMessages(convId) {
  const res = await apiFetch(`${API}/chat/conversations/${convId}/messages`, { headers: getHeaders() });
  return res.json();
}

export function sendMessageStream(convId, text, user, onEvent) {
  const headers = getHeaders();

  return fetch(`${API}/chat/conversations/${convId}/messages`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ text }),
  }).then(async (res) => {
    if (res.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem('eduflow_user');
      window.location.href = '/';
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop();
      for (const part of parts) {
        if (part.startsWith('data: ')) {
          try {
            const data = JSON.parse(part.slice(6));
            onEvent(data);
          } catch {}
        }
      }
    }
  });
}

// --- Students ---
export async function getStudents(user, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const res = await apiFetch(`${API}/students/?${qs}`, { headers: getHeaders() });
  return res.json();
}

export async function createStudent(user, data) {
  const res = await apiFetch(`${API}/students/`, {
    method: 'POST', headers: getHeaders(), body: JSON.stringify(data),
  });
  return res.json();
}

export async function getAllClasses() {
  const res = await apiFetch(`${API}/settings/classes`, { headers: getHeaders() });
  return res.json();
}

// --- Attendance ---
export async function getTodayAttendance(classId) {
  const res = await apiFetch(`${API}/attendance/student/today/${classId}`, { headers: getHeaders() });
  return res.json();
}

export async function bulkMarkAttendance(payload) {
  const res = await apiFetch(`${API}/attendance/student/bulk`, {
    method: 'POST', headers: getHeaders(), body: JSON.stringify(payload),
  });
  return res.json();
}

// --- Fees ---
export async function getFeeTransactions(user, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const res = await apiFetch(`${API}/fees/transactions?${qs}`, { headers: getHeaders() });
  return res.json();
}

export async function recordFeePayment(user, data) {
  const res = await apiFetch(`${API}/fees/transactions`, {
    method: 'POST', headers: getHeaders(), body: JSON.stringify(data),
  });
  return res.json();
}

// --- Tools ---
export async function executeTool(toolId, params) {
  const res = await apiFetch(`${API}/tools/${toolId}/execute`, {
    method: 'POST', headers: getHeaders(), body: JSON.stringify({ params }),
  });
  return res.json();
}

// --- Staff ---
export async function getStaff() {
  const res = await apiFetch(`${API}/staff/`, { headers: getHeaders() });
  return res.json();
}

export async function getPendingLeaves() {
  const res = await apiFetch(`${API}/staff/leaves/pending`, { headers: getHeaders() });
  return res.json();
}

export async function updateLeave(leaveId, status) {
  const res = await apiFetch(`${API}/staff/leaves/${leaveId}`, {
    method: 'PATCH', headers: getHeaders(), body: JSON.stringify({ status }),
  });
  return res.json();
}

// --- Settings ---
export async function getSchoolSettings() {
  const res = await apiFetch(`${API}/settings/school`, { headers: getHeaders() });
  return res.json();
}
