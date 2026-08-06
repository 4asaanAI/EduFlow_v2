import React, { useCallback, useEffect, useRef, useState } from 'react';
import DOMPurify from 'dompurify';
import html2pdf from 'html2pdf.js';
import { Bold, Underline, List, X } from 'lucide-react';

/**
 * Read a document Flo made, correct it, and download the corrected copy.
 *
 * WHY THIS EXISTS (owner request, 2026-08-07). A generated document could only be
 * downloaded. There was no way to read one, fix a sentence and keep the fix short of
 * asking Flo again and hoping for a better answer.
 *
 * NOTHING IS SAVED TO THE SERVER, and that is Abhimanyu's decision of 2026-08-07,
 * not an oversight. The corrected copy leaves as a download and the school's stored
 * copy is unchanged. That is stated on screen in plain words, because an edit panel
 * with no visible save button reads as broken unless it says why.
 *
 * THIS IS THE SAME PATTERN THE QUESTION PAPER CREATOR ALREADY USES
 * (`tools/TeacherTools.js`): contentEditable, sanitised through DOMPurify, a small
 * format toolbar, and downloads built from what is on screen. It was lifted into a
 * shared component rather than copied, so a fix to the sanitising or the PDF export
 * cannot land in one of them and miss the other.
 */
export default function DocumentEditor({ fileName = 'document', html = '', onClose }) {
  const editorRef = useRef(null);
  const [dirty, setDirty] = useState(false);

  // The incoming HTML comes from the server, but it is built from text Flo wrote and
  // from school data, so it is sanitised before it ever reaches the page.
  useEffect(() => {
    if (editorRef.current) {
      editorRef.current.innerHTML = DOMPurify.sanitize(html);
    }
  }, [html]);

  const execFormat = useCallback((cmd, value = null) => {
    editorRef.current?.focus();
    document.execCommand(cmd, false, value);
    setDirty(true);
  }, []);

  const baseName = String(fileName).replace(/\.[^.]+$/, '').replace(/\s+/g, '-') || 'document';
  const liveHtml = () => editorRef.current?.innerHTML || html;

  const downloadPdf = () => {
    // html2canvas cannot capture an off-screen or hidden element, so the copy being
    // printed is placed on screen for the moment it takes, then removed.
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;z-index:9999;background:#fff;overflow:auto;display:flex;justify-content:center;';
    const inner = document.createElement('div');
    inner.style.cssText = 'width:794px;padding:40px 48px;font-family:Arial,sans-serif;font-size:13px;line-height:1.7;color:#111;background:#fff;';
    inner.innerHTML = DOMPurify.sanitize(liveHtml());
    overlay.appendChild(inner);
    document.body.appendChild(overlay);
    html2pdf()
      .set({
        margin: [12, 12, 12, 12],
        filename: `${baseName}-edited.pdf`,
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: { scale: 2, useCORS: true, logging: false, backgroundColor: 'white' },
        jsPDF: { orientation: 'portrait', unit: 'mm', format: 'a4' },
      })
      .from(inner)
      .save()
      .finally(() => document.body.removeChild(overlay));
  };

  const downloadWord = () => {
    const wordHtml = `<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40">
<head><meta charset="UTF-8"><title>${baseName}</title>
<style>body{font-family:Arial,sans-serif;font-size:12pt;line-height:1.6;margin:2cm;}h1{font-size:18pt;}h2{font-size:15pt;}h3{font-size:13pt;}table{border-collapse:collapse;}td,th{border:1px solid #999;padding:6px;}</style></head>
<body>${liveHtml()}</body></html>`;
    // The BOM matters: without it Word opens the file as the system codepage and any
    // Hindi in the document turns into rubbish.
    const blob = new Blob(['﻿', wordHtml], { type: 'application/msword' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${baseName}-edited.doc`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const toolbarBtn = (onClick, icon, title) => (
    <button
      type="button"
      title={title}
      aria-label={title}
      onMouseDown={(e) => { e.preventDefault(); onClick(); }}
      style={{
        background: 'none', border: '1px solid var(--color-border)', borderRadius: 5,
        padding: '4px 8px', color: 'var(--color-text-secondary)', cursor: 'pointer',
        display: 'flex', alignItems: 'center', minHeight: 32,
      }}
    >
      {icon}
    </button>
  );

  const actionBtn = (label, onClick, primary = false) => (
    <button
      type="button"
      onClick={onClick}
      style={{
        padding: '8px 14px', borderRadius: 'var(--radius-md, 10px)',
        border: primary ? 'none' : '1px solid var(--color-border)',
        background: primary ? 'var(--brand-blue-fill, #4f8ff7)' : 'transparent',
        color: primary ? 'var(--on-brand-blue, #fff)' : 'var(--color-text-primary)',
        fontSize: 13, fontWeight: 600, cursor: 'pointer',
      }}
    >
      {label}
    </button>
  );

  return (
    <div
      data-testid="document-editor"
      style={{
        position: 'fixed', inset: 0, zIndex: 60, background: 'rgba(0,0,0,0.5)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 12,
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose?.(); }}
    >
      <div
        role="dialog"
        aria-label={`Edit ${fileName}`}
        style={{
          background: 'var(--color-surface)', border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-lg, 12px)', width: 'min(900px, 100%)',
          maxHeight: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}
      >
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
          padding: '12px 14px', borderBottom: '1px solid var(--color-border)',
        }}>
          <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--color-text-primary)', flex: 1, minWidth: 0, wordBreak: 'break-word' }}>
            {fileName}
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            data-testid="document-editor-close"
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-secondary)', display: 'flex', minHeight: 32 }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Said plainly, and said BEFORE the person spends ten minutes typing. An edit
            panel with no save button is read as broken unless it explains itself. */}
        <div
          data-testid="document-editor-notice"
          style={{
            padding: '9px 14px', fontSize: 12, lineHeight: 1.5,
            color: 'var(--color-text-secondary)', background: 'var(--color-surface-raised)',
            borderBottom: '1px solid var(--color-border)',
          }}
        >
          Changes here are not saved. Correct what you need, then download the corrected
          copy. The version the school already holds stays as it is.
        </div>

        <div style={{
          display: 'flex', gap: 5, padding: '8px 14px', flexWrap: 'wrap', alignItems: 'center',
          borderBottom: '1px solid var(--color-border)',
        }}>
          {toolbarBtn(() => execFormat('bold'), <Bold size={13} />, 'Bold')}
          {toolbarBtn(() => execFormat('underline'), <Underline size={13} />, 'Underline')}
          {toolbarBtn(() => execFormat('insertUnorderedList'), <List size={13} />, 'Bullet list')}
          {toolbarBtn(() => execFormat('formatBlock', 'h2'), <span style={{ fontSize: 12, fontWeight: 700 }}>H2</span>, 'Heading')}
          {toolbarBtn(() => execFormat('formatBlock', 'p'), <span style={{ fontSize: 12 }}>P</span>, 'Normal text')}
          {toolbarBtn(() => execFormat('undo'), <span style={{ fontSize: 12 }}>↩</span>, 'Undo')}
          {toolbarBtn(() => execFormat('redo'), <span style={{ fontSize: 12 }}>↪</span>, 'Redo')}
        </div>

        <div
          ref={editorRef}
          contentEditable
          suppressContentEditableWarning
          role="textbox"
          aria-multiline="true"
          aria-label="Document text"
          data-testid="document-editor-surface"
          onInput={() => setDirty(true)}
          style={{
            flex: 1, minHeight: 260, overflowY: 'auto', padding: 18,
            background: 'var(--color-page)', color: 'var(--color-text-primary)',
            fontSize: 14, lineHeight: 1.7, outline: 'none',
          }}
        />

        <div style={{
          display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center',
          padding: '12px 14px', borderTop: '1px solid var(--color-border)',
        }}>
          {actionBtn('Download PDF', downloadPdf, true)}
          {actionBtn('Download Word', downloadWord)}
          {dirty && (
            <span style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
              Edited. Download to keep your changes.
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
