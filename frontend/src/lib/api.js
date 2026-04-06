const BACKEND = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND}/api`;

function getHeaders(user) {
  return {
    'Content-Type': 'application/json',
    'X-User-Role': user?.role || 'owner',
    'X-User-Id': user?.id || 'user-owner-001',
    'X-User-Name': user?.name || 'Aman',
  };
}

// --- Chat ---
export async function getConversations(user) {
  const res = await fetch(`${API}/chat/conversations`, { headers: getHeaders(user) });
  return res.json();
}

export async function createConversation(user) {
  const res = await fetch(`${API}/chat/conversations`, {
    method: 'POST', headers: getHeaders(user), body: JSON.stringify({}),
  });
  return res.json();
}

export async function updateConversation(convId, update, user) {
  const res = await fetch(`${API}/chat/conversations/${convId}`, {
    method: 'PATCH', headers: getHeaders(user), body: JSON.stringify(update),
  });
  return res.json();
}

export async function deleteConversation(convId, user) {
  const res = await fetch(`${API}/chat/conversations/${convId}`, {
    method: 'DELETE', headers: getHeaders(user),
  });
  return res.json();
}

export async function getMessages(convId, user) {
  const res = await fetch(`${API}/chat/conversations/${convId}/messages`, { headers: getHeaders(user) });
  return res.json();
}

export function sendMessageStream(convId, text, user, onEvent) {
  const headers = getHeaders(user);
  delete headers['Content-Type'];

  return fetch(`${API}/chat/conversations/${convId}/messages`, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  }).then(async (res) => {
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
  const res = await fetch(`${API}/students/?${qs}`, { headers: getHeaders(user) });
  return res.json();
}

export async function createStudent(user, data) {
  const res = await fetch(`${API}/students/`, {
    method: 'POST', headers: getHeaders(user), body: JSON.stringify(data),
  });
  return res.json();
}

export async function getAllClasses(user) {
  const res = await fetch(`${API}/settings/classes`, { headers: getHeaders(user) });
  return res.json();
}

// --- Attendance ---
export async function getTodayAttendance(classId, user) {
  const res = await fetch(`${API}/attendance/student/today/${classId}`, { headers: getHeaders(user) });
  return res.json();
}

export async function bulkMarkAttendance(payload, user) {
  const res = await fetch(`${API}/attendance/student/bulk`, {
    method: 'POST', headers: getHeaders(user), body: JSON.stringify(payload),
  });
  return res.json();
}

// --- Fees ---
export async function getFeeTransactions(user, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const res = await fetch(`${API}/fees/transactions?${qs}`, { headers: getHeaders(user) });
  return res.json();
}

export async function recordFeePayment(user, data) {
  const res = await fetch(`${API}/fees/transactions`, {
    method: 'POST', headers: getHeaders(user), body: JSON.stringify(data),
  });
  return res.json();
}

// --- Tools ---
export async function executeTool(toolId, params, user) {
  const res = await fetch(`${API}/tools/${toolId}/execute`, {
    method: 'POST', headers: getHeaders(user), body: JSON.stringify({ params }),
  });
  return res.json();
}

// --- Staff ---
export async function getStaff(user) {
  const res = await fetch(`${API}/staff/`, { headers: getHeaders(user) });
  return res.json();
}

export async function getPendingLeaves(user) {
  const res = await fetch(`${API}/staff/leaves/pending`, { headers: getHeaders(user) });
  return res.json();
}

export async function updateLeave(leaveId, status, user) {
  const res = await fetch(`${API}/staff/leaves/${leaveId}`, {
    method: 'PATCH', headers: getHeaders(user), body: JSON.stringify({ status }),
  });
  return res.json();
}

// --- Settings ---
export async function getSchoolSettings(user) {
  const res = await fetch(`${API}/settings/school`, { headers: getHeaders(user) });
  return res.json();
}
