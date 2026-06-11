import { getAccessToken, redirectToLoginOnce, refreshAccessToken } from './authSession';

const _rawBackend = process.env.REACT_APP_BACKEND_URL || '';
// Force HTTPS when the page is served over HTTPS (prevents mixed-content blocks on Amplify/CloudFront)
const BACKEND = typeof window !== 'undefined' && window.location.protocol === 'https:'
  ? _rawBackend.replace(/^http:\/\/(?!localhost)/, 'https://')
  : _rawBackend;
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
export async function apiFetch(url, options = {}) {
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
    redirectToLoginOnce('/');
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

export function sendMessageStream(convId, text, user, onEvent, sessionId = null) {
  const headers = getHeaders();
  const chatSessionId = sessionId || getBrowserSseSessionId();

  return fetch(`${API}/chat/conversations/${convId}/messages`, {
    method: 'POST',
    headers: {
      ...headers,
      'X-SSE-Session-ID': chatSessionId,
    },
    credentials: 'include',
    body: JSON.stringify({ text, session_id: chatSessionId }),
  }).then(async (res) => {
    if (res.status === 401) {
      // SSE chat path: 401 mid-stream redirects immediately; retrying would
      // duplicate the in-progress conversation message and AI token debit.
      redirectToLoginOnce('/');
      return;
    }

    if (!res.ok || !res.body) {
      const message = await res.text().catch(() => '');
      throw new Error(message || `Chat request failed (${res.status})`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let receivedDone = false;

    try {
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
              if (data?.type === 'done') receivedDone = true;
              onEvent(data);
            } catch {}
          }
        }
      }
    } catch {
      onEvent({ type: 'thinking_clear' });
      onEvent({ type: 'stream_error', retryable: true, reason: 'stream_network_error' });
      return;
    }

    if (!receivedDone) {
      onEvent({ type: 'thinking_clear' });
      onEvent({ type: 'stream_error', retryable: true, reason: 'stream_closed_without_done' });
    }
  }).catch(() => {
    onEvent({ type: 'thinking_clear' });
    onEvent({ type: 'stream_error', retryable: true, reason: 'stream_network_error' });
  });
}

export function getBrowserSseSessionId() {
  const key = 'eduflow-sse-session-id';
  let sessionId = sessionStorage.getItem(key);
  if (!sessionId) {
    const browserCrypto = typeof crypto !== 'undefined' ? crypto : null;
    sessionId = (browserCrypto?.randomUUID?.() || `tab-${Date.now()}-${Math.random().toString(16).slice(2)}`);
    sessionStorage.setItem(key, sessionId);
  }
  return sessionId;
}

export function subscribeSSE(path, onEvent, { onReconnect, reconnect = true, maxRetries = Infinity } = {}) {
  let stopped = false;
  let controller = null;
  const sessionId = getBrowserSseSessionId();
  let retryCount = 0;
  let retryTimer = null;

  const scheduleReconnect = () => {
    if (stopped || !reconnect || retryCount >= maxRetries) return;
    retryCount += 1;
    const delayMs = Math.min((2 ** (retryCount - 1)) * 500, 8000);
    onEvent({ type: 'sse_reconnecting', retryCount, delayMs });
    retryTimer = setTimeout(open, delayMs);
  };

  const open = async () => {
    if (stopped) return;
    controller = new AbortController();
    try {
      const res = await fetch(`${API}${path}`, {
        method: 'GET',
        headers: {
          ...getHeaders(),
          'X-SSE-Session-ID': sessionId,
        },
        credentials: 'include',
        signal: controller.signal,
      });
      if (!res.ok || !res.body) {
        scheduleReconnect();
        return;
      }
      retryCount = 0;

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (!stopped) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop();
        for (const part of parts) {
          if (!part.startsWith('data: ')) continue;
          try {
            onEvent(JSON.parse(part.slice(6)));
          } catch {}
        }
      }
      scheduleReconnect();
    } catch (err) {
      if (!stopped && err.name !== 'AbortError') {
        scheduleReconnect();
      }
    }
  };

  const handleVisibility = () => {
    if (document.visibilityState !== 'visible' || stopped) return;
    if (controller) controller.abort();
    if (onReconnect) onReconnect();
    open();
  };

  document.addEventListener('visibilitychange', handleVisibility);
  open();

  return () => {
    stopped = true;
    document.removeEventListener('visibilitychange', handleVisibility);
    if (retryTimer) clearTimeout(retryTimer);
    if (controller) controller.abort();
  };
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

export async function getStudentStrengthStats() {
  const res = await apiFetch(`${API}/students/strength`, { headers: getHeaders() });
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

export async function getStudent(studentId) {
  const res = await apiFetch(`${API}/students/${studentId}`, { headers: getHeaders() });
  return res.json();
}

export async function upsertGuardians(studentId, guardiansArray) {
  const res = await apiFetch(`${API}/students/${studentId}/guardians`, {
    method: 'PUT', headers: getHeaders(), body: JSON.stringify(guardiansArray),
  });
  return res.json();
}

export async function uploadGuardianPhoto(studentId, guardianId, file) {
  const body = new FormData();
  body.append('file', file);
  const headers = getHeaders();
  delete headers['Content-Type'];
  const res = await apiFetch(`${API}/students/${studentId}/guardians/${guardianId}/photo`, {
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

export async function recordFeePayment(user, data, idempotencyKey) {
  const headers = getHeaders();
  if (idempotencyKey) headers['Idempotency-Key'] = idempotencyKey;
  const res = await apiFetch(`${API}/fees/transactions`, {
    method: 'POST', headers, body: JSON.stringify(data),
  });
  return res.json();
}

export async function correctFeeTransaction(transactionId, data) {
  const res = await apiFetch(`${API}/fees/transactions/${transactionId}/correct`, {
    method: 'PATCH', headers: getHeaders(), body: JSON.stringify(data),
  });
  return res.json();
}

export async function deleteFeeTransaction(transactionId) {
  const res = await apiFetch(`${API}/fees/transactions/${transactionId}`, {
    method: 'DELETE', headers: getHeaders(),
  });
  return res.json();
}

export async function getFeeSummary(params = {}) {
  const qs = new URLSearchParams(params).toString();
  const res = await apiFetch(`${API}/fees/summary?${qs}`, { headers: getHeaders() });
  return res.json();
}

export async function getStudentFeeStatus(studentId) {
  const res = await apiFetch(`${API}/fees/status/${studentId}`, { headers: getHeaders() });
  return res.json();
}

export async function createFeeContactLog(data) {
  const res = await apiFetch(`${API}/fees/contact-log`, {
    method: 'POST', headers: getHeaders(), body: JSON.stringify(data),
  });
  return res.json();
}

export async function getDiscountTypes(params = {}) {
  const qs = new URLSearchParams(params).toString();
  const res = await apiFetch(`${API}/fees/discount-types?${qs}`, { headers: getHeaders() });
  return res.json();
}

export async function createDiscountType(data) {
  const res = await apiFetch(`${API}/fees/discount-types`, {
    method: 'POST', headers: getHeaders(), body: JSON.stringify(data),
  });
  return res.json();
}

export async function updateDiscountType(discountTypeId, data) {
  const res = await apiFetch(`${API}/fees/discount-types/${discountTypeId}`, {
    method: 'PATCH', headers: getHeaders(), body: JSON.stringify(data),
  });
  return res.json();
}

export async function applyFeeDiscount(data) {
  const res = await apiFetch(`${API}/fees/discounts/apply`, {
    method: 'POST', headers: getHeaders(), body: JSON.stringify(data),
  });
  return res.json();
}

export async function approveFeeDiscount(applicationId) {
  const res = await apiFetch(`${API}/fees/discounts/${applicationId}/approve`, {
    method: 'POST', headers: getHeaders(),
  });
  return res.json();
}

export async function rejectFeeDiscount(applicationId, reason) {
  const res = await apiFetch(`${API}/fees/discounts/${applicationId}/reject`, {
    method: 'POST', headers: getHeaders(), body: JSON.stringify({ reason }),
  });
  return res.json();
}

export async function getSalaryStructures() {
  const res = await apiFetch(`${API}/fees/payroll/structures`, { headers: getHeaders() });
  return res.json();
}

export async function upsertSalaryStructure(data) {
  const res = await apiFetch(`${API}/fees/payroll/structures`, {
    method: 'POST', headers: getHeaders(), body: JSON.stringify(data),
  });
  return res.json();
}

export async function createSalaryDisbursement(data) {
  const res = await apiFetch(`${API}/fees/payroll/disbursements`, {
    method: 'POST', headers: getHeaders(), body: JSON.stringify(data),
  });
  return res.json();
}

export async function getFeeDiscounts(studentId) {
  const res = await apiFetch(`${API}/fees/discounts/${studentId}`, { headers: getHeaders() });
  return res.json();
}

export async function getDiscountSummary() {
  const res = await apiFetch(`${API}/fees/discount-summary`, { headers: getHeaders() });
  return res.json();
}

export async function triggerFeeSync() {
  const res = await apiFetch(`${API}/fees/sync/trigger`, { method: 'POST', headers: getHeaders() });
  return res.json();
}

export async function getFeeSyncJob(syncJobId) {
  const res = await apiFetch(`${API}/fees/sync/${syncJobId}`, { headers: getHeaders() });
  return res.json();
}

export async function resolveFeeSyncConflict(syncJobId, data) {
  const res = await apiFetch(`${API}/fees/sync/${syncJobId}/resolve-conflict`, {
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

export async function updateLeave(leaveId, status, reason = 'Reviewed in staff tracker') {
  const body = status === 'rejected' ? { status, rejection_reason: reason } : { status };
  const res = await apiFetch(`${API}/staff/leaves/${leaveId}`, {
    method: 'PATCH', headers: getHeaders(), body: JSON.stringify(body),
  });
  return res.json();
}

export async function createLeaveRequest(data) {
  const res = await apiFetch(`${API}/operations/leave-requests`, {
    method: 'POST', headers: getHeaders(), body: JSON.stringify(data),
  });
  return res.json();
}

export async function getOperationLeaveRequests(params = {}) {
  const qs = new URLSearchParams(params).toString();
  const res = await apiFetch(`${API}/operations/leave-requests?${qs}`, { headers: getHeaders() });
  return res.json();
}

export async function createApprovalRequest(data) {
  const res = await apiFetch(`${API}/operations/approval-requests`, {
    method: 'POST', headers: getHeaders(), body: JSON.stringify(data),
  });
  return res.json();
}

export async function getApprovalRequests(params = {}) {
  const qs = new URLSearchParams(params).toString();
  const res = await apiFetch(`${API}/operations/approval-requests?${qs}`, { headers: getHeaders() });
  return res.json();
}

export async function decideApprovalRequest(approvalId, data) {
  const res = await apiFetch(`${API}/operations/approval-requests/${approvalId}/decide`, {
    method: 'PATCH', headers: getHeaders(), body: JSON.stringify(data),
  });
  return res.json();
}

// --- Settings ---
export async function getSchoolSettings() {
  const res = await apiFetch(`${API}/settings/school`, { headers: getHeaders() });
  return res.json();
}

// --- Chat file upload ---
export async function uploadChatFile(file) {
  const form = new FormData();
  form.append('file', file);
  const token = getAccessToken();
  const res = await fetch(`${API}/chat/upload`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  return res.json();
}

// --- Payroll ---
export async function listPayrollDisbursements(month) {
  const qs = month ? `?month=${encodeURIComponent(month)}` : '';
  const res = await apiFetch(`${API}/payroll/disbursements${qs}`, { headers: getHeaders() });
  return res.json();
}

export async function listPayrollStructures() {
  const res = await apiFetch(`${API}/payroll/structures`, { headers: getHeaders() });
  return res.json();
}

export async function createPayrollStructure(data) {
  const res = await apiFetch(`${API}/payroll/structures`, {
    method: 'POST', headers: getHeaders(), body: JSON.stringify(data),
  });
  return res.json();
}

export async function createPayrollDisbursement(data) {
  const res = await apiFetch(`${API}/payroll/disburse`, {
    method: 'POST', headers: getHeaders(), body: JSON.stringify(data),
  });
  return res.json();
}

export async function markDisbursementProcessed(disbursementId) {
  const res = await apiFetch(`${API}/payroll/disbursements/${disbursementId}/process`, {
    method: 'PATCH', headers: getHeaders(),
  });
  return res.json();
}

export async function changePassword(currentPassword, newPassword) {
  const res = await apiFetch(`${API}/auth/change-password`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
  return res.json();
}

export async function fetchPlatformHealth() {
  const res = await apiFetch(`${API}/operator/platform-health`, { headers: getHeaders() });
  return res.json();
}

export async function deactivateSchool(schoolId) {
  const res = await apiFetch(`${API}/operator/schools/${encodeURIComponent(schoolId)}/deactivate`, {
    method: 'PATCH',
    headers: getHeaders(),
  });
  return res.json();
}

// Transport Optimisation (Story 7-46)

export async function geocodeAddress(address) {
  const res = await apiFetch(`${API}/transport/geocode`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ address }),
  });
  return res.json();
}

export async function setStudentCoordinates(studentId, lat, lng) {
  const res = await apiFetch(`${API}/transport/students/${encodeURIComponent(studentId)}/coordinates`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify({ lat, lng }),
  });
  return res.json();
}

export async function setZoneCentroid(zoneId, lat, lng) {
  const res = await apiFetch(`${API}/transport/zones/${encodeURIComponent(zoneId)}/centroid`, {
    method: 'PATCH',
    headers: getHeaders(),
    body: JSON.stringify({ lat, lng }),
  });
  return res.json();
}

export async function fetchRouteSuggestion(studentId) {
  const res = await apiFetch(`${API}/transport/suggest-route?student_id=${encodeURIComponent(studentId)}`, {
    headers: getHeaders(),
  });
  return res.json();
}

export async function fetchClusterAnalysis() {
  const res = await apiFetch(`${API}/transport/cluster-analysis`, {
    headers: getHeaders(),
  });
  return res.json();
}

// ── WhatsApp reminders (Story 7-40) ──────────────────────────────────────────

export async function getWhatsappDefaulters() {
  const res = await apiFetch(`${API}/sms/whatsapp-defaulters`, {
    headers: getHeaders(),
  });
  return res.json();
}

export async function sendFeeReminders(recipients) {
  const res = await apiFetch(`${API}/sms/whatsapp-fee-reminders`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ recipients }),
  });
  return res.json();
}

export async function adminResetPassword(userId, newPassword) {
  const res = await apiFetch(`${API}/auth/admin/users/${encodeURIComponent(userId)}/reset-password`, {
    method: 'POST',
    headers: { ...getHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ new_password: newPassword }),
  });
  return res.json();
}

export async function sendAttendanceAlerts(recipients) {
  const res = await apiFetch(`${API}/sms/whatsapp-attendance-alerts`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({ recipients }),
  });
  return res.json();
}

export async function getMyTokenUsage() {
  const res = await apiFetch(`${API}/tokens/usage/me`, { headers: getHeaders() });
  return res.json();
}

export async function getTokenPlans() {
  const res = await apiFetch(`${API}/tokens/packs`, { headers: getHeaders() });
  return res.json();
}

export async function createSubscriptionCheckout(planId) {
  const origin = window.location.origin;
  const res = await apiFetch(`${API}/tokens/create-subscription-session`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({
      plan_id: planId,
      success_url: `${origin}?recharge=success`,
      cancel_url: `${origin}?recharge=cancel`,
    }),
  });
  return res.json();
}

export async function createTopupCheckout(packId) {
  const origin = window.location.origin;
  const res = await apiFetch(`${API}/tokens/create-checkout-session`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify({
      pack_id: packId,
      success_url: `${origin}?recharge=success`,
      cancel_url: `${origin}?recharge=cancel`,
    }),
  });
  return res.json();
}


