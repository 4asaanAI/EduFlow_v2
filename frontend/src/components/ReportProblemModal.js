/**
 * R4-5 - "Report a problem", available to every profile.
 *
 * Three things this screen has to get right, and each one is a decision rather than a
 * layout choice:
 *
 * 1. **The picture is shown before it is sent.** Not to protect the data - Layaa AI
 *    already holds most of the school's records, which is settled (decision 14) - but
 *    because a person should be able to see what they just sent. It is captured, shown
 *    at a size where the words on it are legible, and can be removed with one button.
 *
 * 2. **The reply is the truth, whatever it is.** "Saved here but it has not reached
 *    Layaa AI yet" is a perfectly good outcome and is shown as one, in those words. The
 *    old bulk messaging route recorded every recipient as "not configured" and returned
 *    success; that is the failure being avoided here.
 *
 * 3. **Nothing is raised silently.** The reference comes back and stays on screen until
 *    the person dismisses it.
 *
 * The screenshot is taken with html2canvas, which is ALREADY a dependency of this app
 * (it is what the PDF exports use). No new package, so no new cost, which is the rule
 * for the whole of Release 4.
 */

import React, { useState } from 'react';
import { X, Camera, Send, Trash2, AlertCircle, CheckCircle2 } from 'lucide-react';
import { raisePlatformTicket } from '../lib/api';

const KINDS = [
  { value: 'bug', label: 'Something is broken' },
  { value: 'incident', label: 'Something has stopped working for everybody' },
  { value: 'support', label: 'I need help with something' },
  { value: 'feedback', label: 'A suggestion' },
];

const field = {
  width: '100%', padding: '10px 12px', borderRadius: 8,
  border: '1px solid var(--color-border)', background: 'var(--color-bg)',
  color: 'var(--color-text)', fontSize: 14, fontFamily: 'inherit',
};

const label = { display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 6, color: 'var(--color-text-secondary)' };

export default function ReportProblemModal({ onClose }) {
  const [title, setTitle] = useState('');
  const [detail, setDetail] = useState('');
  const [expected, setExpected] = useState('');
  const [kind, setKind] = useState('bug');
  const [shot, setShot] = useState(null);
  const [capturing, setCapturing] = useState(false);
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  async function capture() {
    setCapturing(true);
    setError('');
    try {
      // Imported here rather than at the top of the file so the library is only
      // fetched by somebody who actually asks for a picture. It is a large module and
      // most people opening this screen will type words and press send.
      const html2canvas = (await import('html2canvas')).default;
      // The dialog itself is hidden for the shot: a picture of the form you are filling
      // in tells us nothing about the screen you were complaining about.
      const dialog = document.getElementById('report-problem-dialog');
      if (dialog) dialog.style.visibility = 'hidden';
      let canvas;
      try {
        canvas = await html2canvas(document.body, { scale: 1, useCORS: true, logging: false });
      } finally {
        if (dialog) dialog.style.visibility = 'visible';
      }
      // JPEG at 0.7 rather than PNG. A full-page PNG runs to several megabytes and
      // images are the quiet cost in this release; text on a screenshot stays legible.
      setShot(canvas.toDataURL('image/jpeg', 0.7));
    } catch {
      setError('The picture of your screen could not be taken. You can still send the report without one.');
    } finally {
      setCapturing(false);
    }
  }

  async function send() {
    if (!title.trim()) { setError('Say in one line what is wrong.'); return; }
    setSending(true);
    setError('');
    try {
      const res = await raisePlatformTicket({
        title: title.trim(),
        detail: detail.trim() || null,
        kind,
        context: expected.trim() ? { what_they_expected: expected.trim() } : {},
        app_url: window.location.href,
        screenshot_base64: shot || undefined,
        screenshot_mime: shot ? 'image/jpeg' : undefined,
      });
      if (res.success) setResult(res.data);
      else setError(res.detail || 'Couldn\'t save the report. Try again.');
    } catch {
      setError('Couldn\'t send the report. Try again.');
    } finally {
      setSending(false);
    }
  }

  return (
    <div
      role="dialog" aria-modal="true" aria-label="Report a problem"
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 1000,
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        id="report-problem-dialog"
        style={{
          background: 'var(--color-surface)', borderRadius: 12, width: '100%', maxWidth: 560,
          maxHeight: '90vh', overflowY: 'auto', padding: 20,
          border: '1px solid var(--color-border)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
          <h2 style={{ margin: 0, fontSize: 17, fontWeight: 700, color: 'var(--color-text)' }}>Report a problem</h2>
          <button type="button" aria-label="Close" onClick={onClose}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-secondary)', padding: 4 }}>
            <X size={18} />
          </button>
        </div>

        {result ? (
          <div style={{ paddingTop: 12 }}>
            <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
              {/* Delivered and not-delivered look DIFFERENT, and both are shown. A
                  report saved here but not yet sent is a real outcome, not an error to
                  hide behind a tick. */}
              {result.delivered
                ? <CheckCircle2 size={20} color="#10b981" style={{ flexShrink: 0, marginTop: 1 }} />
                : <AlertCircle size={20} color="#f59e0b" style={{ flexShrink: 0, marginTop: 1 }} />}
              <div>
                <p style={{ margin: 0, fontSize: 14, color: 'var(--color-text)' }}>{result.message}</p>
                <p style={{ margin: '8px 0 0', fontSize: 12, color: 'var(--color-text-secondary)' }}>
                  Your reference is <strong>{String(result.id).slice(0, 8)}</strong>. You can see this report and
                  what happened to it under your own reports at any time.
                </p>
              </div>
            </div>
            <button type="button" onClick={onClose}
              style={{ ...field, width: 'auto', marginTop: 16, cursor: 'pointer', fontWeight: 600, background: 'var(--color-primary, #4f8ff7)', color: '#fff', border: 'none' }}>
              Done
            </button>
          </div>
        ) : (
          <>
            <p style={{ margin: '0 0 16px', fontSize: 13, color: 'var(--color-text-secondary)' }}>
              This goes to Layaa AI, who build this platform. Use it when the platform itself is not
              doing what it should and nobody here can put it right.
            </p>

            <div style={{ marginBottom: 12 }}>
              <label htmlFor="rp-title" style={label}>What is wrong?</label>
              <input id="rp-title" style={field} value={title} maxLength={200}
                placeholder="One line, for example: the fee collection screen will not open"
                onChange={(e) => setTitle(e.target.value)} />
            </div>

            <div style={{ marginBottom: 12 }}>
              <label htmlFor="rp-kind" style={label}>What sort of problem is it?</label>
              <select id="rp-kind" style={field} value={kind} onChange={(e) => setKind(e.target.value)}>
                {KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
              </select>
            </div>

            <div style={{ marginBottom: 12 }}>
              <label htmlFor="rp-detail" style={label}>What were you doing when it happened?</label>
              <textarea id="rp-detail" rows={3} style={{ ...field, resize: 'vertical' }} value={detail}
                placeholder="It helps to know the steps you took"
                onChange={(e) => setDetail(e.target.value)} />
            </div>

            <div style={{ marginBottom: 16 }}>
              <label htmlFor="rp-expected" style={label}>What did you expect to happen?</label>
              <input id="rp-expected" style={field} value={expected}
                onChange={(e) => setExpected(e.target.value)} />
            </div>

            <div style={{ marginBottom: 16 }}>
              {shot ? (
                <>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span style={{ ...label, marginBottom: 0 }}>This is the picture that will be sent</span>
                    <button type="button" onClick={() => setShot(null)}
                      style={{ display: 'flex', alignItems: 'center', gap: 5, background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444', fontSize: 12, fontWeight: 600 }}>
                      <Trash2 size={13} /> Remove
                    </button>
                  </div>
                  <img src={shot} alt="The picture of your screen that will be sent"
                    style={{ width: '100%', borderRadius: 8, border: '1px solid var(--color-border)' }} />
                </>
              ) : (
                <button type="button" onClick={capture} disabled={capturing}
                  style={{ ...field, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, cursor: capturing ? 'default' : 'pointer', fontWeight: 600 }}>
                  <Camera size={15} />
                  {capturing ? 'Taking the picture...' : 'Add a picture of this screen'}
                </button>
              )}
            </div>

            {error && (
              <p role="alert" style={{ margin: '0 0 12px', fontSize: 13, color: '#ef4444' }}>{error}</p>
            )}

            <button type="button" onClick={send} disabled={sending}
              style={{
                ...field, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                cursor: sending ? 'default' : 'pointer', fontWeight: 600,
                background: 'var(--color-primary, #4f8ff7)', color: '#fff', border: 'none',
              }}>
              <Send size={15} />{sending ? 'Sending...' : 'Send this report'}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
