import { clearAuthSession, getAccessToken, refreshAccessToken } from './authSession';

const BACKEND = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND}/api`;

/**
 * Build headers for API requests.
 * Uses the in-memory JWT access token.
 */
function getHeaders() {
  const headers = {
    'Content-Type': 'application/json',
  };

  const token = getAccessToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  return headers;
}

/**
 * Wrapper around fetch that refreshes once on 401 before redirecting.
 */
async function apiFetch(url, options = {}) {
  let res = await fetch(url, { credentials: 'include', ...options });

  if (res.status === 401) {
    try {
      await refreshAccessToken(API);
      const retryOptions = {
        ...options,
        headers: {
          ...(options.headers || {}),
          ...(getAccessToken() ? { Authorization: `Bearer ${getAccessToken()}` } : {}),
        },
      };
      res = await fetch(url, { credentials: 'include', ...retryOptions });
      if (res.status !== 401) return res;
    } catch {}
    clearAuthSession();
    window.location.href = '/';
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
    credentials: 'include',
    body: JSON.stringify({ text }),
  }).then(async (res) => {
    if (res.status === 401) {
      clearAuthSession();
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

export async function updateStudent(studentId, data) {
  const res = await apiFetch(`${API}/students/${studentId}`, {
    method: 'PATCH', headers: getHeaders(), body: JSON.stringify(data),
  });
  return res.json();
}

export async function deactivateStudent(studentId) {
  const res = await apiFetch(`${API}/students/${studentId}`, {
    method: 'DELETE', headers: getHeaders(),
  });
  return res.json();
}

export async function eraseStudent(studentId, reason) {
  const body = new FormData();
  body.append('reason', reason);
  const headers = getHeaders();
  delete headers['Content-Type'];
  const res = await apiFetch(`${API}/students/${studentId}/erase`, {
    method: 'POST', headers, body,
  });
  return res.json();
}

export async function uploadStudentPhoto(studentId, file) {
  const body = new FormData();
  body.append('file', file);
  const headers = getHeaders();
  delete headers['Content-Type'];
  const res = await apiFetch(`${API}/students/${studentId}/photo`, {
    method: 'POST', headers, body,
  });
  return res.json();
}

export async function getAllClasses() {
  const res = await apiFetch(`${API}/settings/classes`, { headers: getHeaders() });
  return res.json();
}

// --- Attendance ---
export async function getTodayAttendance(classId, date) {
  const qs = date ? `?date=${encodeURIComponent(date)}` : '';
  const res = await apiFetch(`${API}/attendance/student/today/${classId}${qs}`, { headers: getHeaders() });
  return res.json();
}

export async function bulkMarkAttendance(payload) {
  const res = await apiFetch(`${API}/attendance/student/bulk`, {
    method: 'POST', headers: getHeaders(), body: JSON.stringify(payload),
  });
  return res.json();
}

export async function createManualAttendance(payload) {
  const res = await apiFetch(`${API}/attendance`, {
    method: 'POST', headers: getHeaders(), body: JSON.stringify(payload),
  });
  return res.json();
}

export async function correctAttendance(attendanceId, payload) {
  const res = await apiFetch(`${API}/attendance/${attendanceId}/correct`, {
    method: 'PATCH', headers: getHeaders(), body: JSON.stringify(payload),
  });
  return res.json();
}

export async function getAttendanceHistory(attendanceId) {
  const res = await apiFetch(`${API}/attendance/${attendanceId}/history`, { headers: getHeaders() });
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
export async function getStaff(params = {}) {
  const qs = new URLSearchParams(params).toString();
  const res = await apiFetch(`${API}/staff/?${qs}`, { headers: getHeaders() });
  return res.json();
}

export async function createStaff(data) {
  const res = await apiFetch(`${API}/staff/`, {
    method: 'POST', headers: getHeaders(), body: JSON.stringify(data),
  });
  return res.json();
}

export async function updateStaff(staffId, data) {
  const res = await apiFetch(`${API}/staff/${staffId}`, {
    method: 'PATCH', headers: getHeaders(), body: JSON.stringify(data),
  });
  return res.json();
}

export async function deactivateStaff(staffId) {
  const res = await apiFetch(`${API}/staff/${staffId}`, {
    method: 'DELETE', headers: getHeaders(),
  });
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
