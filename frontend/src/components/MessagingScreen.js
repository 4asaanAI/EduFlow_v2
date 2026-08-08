import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowLeft,
  Check,
  CheckCheck,
  Edit3,
  MessageCircle,
  MoreHorizontal,
  Pencil,
  Plus,
  Reply,
  Search,
  Send,
  Trash2,
  UserRound,
  Users,
  X,
} from 'lucide-react';

import { useMessaging } from '@/contexts/MessagingContext';
import { useUser } from '@/contexts/UserContext';
import {
  createDirectMessageThread,
  createMessageGroup,
  deletePlatformMessage,
  editPlatformMessage,
  getPlatformMessages,
  markMessageThreadRead,
  sendMessageTyping,
  sendPlatformMessage,
  updateMessageGroup,
} from '@/lib/api';
import './MessagingScreen.css';


function initials(name = '') {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join('').toUpperCase() || '?';
}

function roleLabel(contact) {
  if (contact?.role === 'owner') return 'School owner';
  const labels = { principal: 'Principal', accountant: 'Accountant', management: 'Admin office' };
  return labels[contact?.sub_category] || 'School profile';
}

function formatTime(value, includeDate = false) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const today = new Date();
  const sameDay = date.toDateString() === today.toDateString();
  if (!sameDay || includeDate) {
    return new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', ...(includeDate ? { year: 'numeric' } : {}) }).format(date);
  }
  return new Intl.DateTimeFormat('en-IN', { hour: 'numeric', minute: '2-digit' }).format(date);
}

function Avatar({ name, online = false, group = false, size = 40 }) {
  return (
    <div className="message-avatar" style={{ width: size, height: size, minWidth: size }} aria-hidden="true">
      {group ? <Users size={Math.round(size * 0.45)} /> : initials(name)}
      {online && <span className="message-online-dot" />}
    </div>
  );
}

function ReceiptTicks({ receipt }) {
  if (!receipt) return null;
  const status = receipt.status || 'sent';
  const title = status === 'read'
    ? `Read by ${receipt.read_count || 0} of ${receipt.recipient_count || 0}`
    : status === 'delivered'
      ? `Delivered to ${receipt.delivered_count || 0} of ${receipt.recipient_count || 0}`
      : 'Sent';
  return status === 'sent'
    ? <Check className="message-ticks" size={14} aria-label={title} />
    : <CheckCheck className={`message-ticks ${status === 'read' ? 'is-read' : ''}`} size={15} aria-label={title} />;
}

function ContactStatus({ thread, contacts, typing }) {
  if (typing) return <span className="message-typing">{typing} typing...</span>;
  if (thread.kind === 'group') return <span>{thread.members?.length || 0} members</span>;
  const other = thread.members?.find((member) => !member.is_self) || thread.members?.[0];
  const live = contacts.find((contact) => contact.id === other?.id) || other;
  if (live?.online) return <span className="message-online-text">Online</span>;
  if (live?.last_seen_at) return <span>Last seen {formatTime(live.last_seen_at, true)}</span>;
  return <span>{roleLabel(live)}</span>;
}

function ComposeDialog({ mode, contacts, currentUserId, thread, onClose, onCreated, onUpdated }) {
  const [dialogMode, setDialogMode] = useState(mode || 'direct');
  const [name, setName] = useState(thread?.name || '');
  const [selected, setSelected] = useState(() => new Set(
    (thread?.member_ids || []).filter((id) => id !== currentUserId)
  ));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const people = contacts.filter((contact) => !contact.is_self);
  const editing = dialogMode === 'edit';

  const openDirect = async (contact) => {
    setSaving(true);
    setError('');
    try {
      const response = await createDirectMessageThread(contact.id);
      onCreated(response.data);
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  };

  const saveGroup = async () => {
    setSaving(true);
    setError('');
    try {
      if (editing) {
        const response = await updateMessageGroup(thread.id, { name, member_ids: [...selected] });
        onUpdated(response.data);
      } else {
        const response = await createMessageGroup(name, [...selected]);
        onCreated(response.data);
      }
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  };

  const toggle = (id) => setSelected((current) => {
    const next = new Set(current);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    return next;
  });

  return (
    <div className="message-dialog-layer" role="presentation">
      <button className="message-dialog-backdrop" aria-label="Close" onClick={onClose} />
      <div className="message-dialog" role="dialog" aria-modal="true" aria-labelledby="message-dialog-title">
        <div className="message-dialog-header">
          <div>
            <h2 id="message-dialog-title">{editing ? 'Group details' : dialogMode === 'group' ? 'New group' : 'New message'}</h2>
            <p>{editing ? `${thread.members?.length || 0} current members` : 'Aaryans leadership and office'}</p>
          </div>
          <button className="message-icon-btn" onClick={onClose} aria-label="Close" title="Close"><X size={18} /></button>
        </div>

        {!editing && (
          <div className="message-mode-switch" role="tablist" aria-label="Conversation type">
            <button className={dialogMode === 'direct' ? 'is-active' : ''} onClick={() => setDialogMode('direct')} role="tab" aria-selected={dialogMode === 'direct'}>
              <UserRound size={16} /> Direct
            </button>
            <button className={dialogMode === 'group' ? 'is-active' : ''} onClick={() => setDialogMode('group')} role="tab" aria-selected={dialogMode === 'group'}>
              <Users size={16} /> Group
            </button>
          </div>
        )}

        {dialogMode === 'direct' && !editing ? (
          <div className="message-contact-picker">
            {people.map((contact) => (
              <button key={contact.id} onClick={() => openDirect(contact)} disabled={saving}>
                <Avatar name={contact.name} online={contact.online} size={38} />
                <span><strong>{contact.name}</strong><small>{roleLabel(contact)}</small></span>
                <MessageCircle size={17} />
              </button>
            ))}
          </div>
        ) : (
          <>
            <label className="message-field">
              <span>Group name</span>
              <input value={name} onChange={(event) => setName(event.target.value)} maxLength={80} autoFocus />
            </label>
            <div className="message-member-list">
              {people.map((contact) => (
                <label key={contact.id}>
                  <input type="checkbox" checked={selected.has(contact.id)} onChange={() => toggle(contact.id)} />
                  <Avatar name={contact.name} online={contact.online} size={36} />
                  <span><strong>{contact.name}</strong><small>{roleLabel(contact)}</small></span>
                </label>
              ))}
            </div>
            <div className="message-dialog-actions">
              <button className="message-secondary-btn" onClick={onClose}>Cancel</button>
              <button className="message-primary-btn" onClick={saveGroup} disabled={saving || !name.trim() || selected.size < 2}>
                {saving ? 'Saving...' : editing ? 'Save' : 'Create group'}
              </button>
            </div>
          </>
        )}
        {error && <div className="message-error" role="alert">{error}</div>}
      </div>
    </div>
  );
}

export default function MessagingScreen() {
  const { currentUser } = useUser();
  const messaging = useMessaging();
  const { refreshContacts, refreshThreads, setViewingThread } = messaging;
  const [selectedId, setSelectedId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [search, setSearch] = useState('');
  const [composer, setComposer] = useState('');
  const [replyingTo, setReplyingTo] = useState(null);
  const [editing, setEditing] = useState(null);
  const [typingName, setTypingName] = useState('');
  const [dialog, setDialog] = useState(null);
  const [error, setError] = useState('');
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const lastTypingRef = useRef(0);
  const typingTimerRef = useRef(null);

  const selectedThread = messaging.threads.find((thread) => thread.id === selectedId) || null;
  const filteredThreads = useMemo(() => {
    const query = search.trim().toLocaleLowerCase('en-IN');
    if (!query) return messaging.threads;
    return messaging.threads.filter((thread) => (
      thread.title || ''
    ).toLocaleLowerCase('en-IN').includes(query));
  }, [messaging.threads, search]);

  const loadMessages = useCallback(async (threadId, markRead = true) => {
    if (!threadId) return;
    setLoadingMessages(true);
    setError('');
    try {
      const response = await getPlatformMessages(threadId);
      setMessages(response.data || []);
      if (markRead) {
        await markMessageThreadRead(threadId);
        await refreshThreads();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingMessages(false);
    }
  }, [refreshThreads]);

  useEffect(() => {
    setViewingThread(true, selectedId);
    return () => setViewingThread(false, null);
  }, [selectedId, setViewingThread]);

  useEffect(() => {
    if (selectedId) loadMessages(selectedId);
    else setMessages([]);
  }, [loadMessages, selectedId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ block: 'end' });
  }, [messages, typingName]);

  useEffect(() => {
    const event = messaging.liveEvent;
    if (!event) return;
    if (event.type === 'typing' && event.thread_id === selectedId) {
      setTypingName(event.name || 'Someone');
      clearTimeout(typingTimerRef.current);
      typingTimerRef.current = setTimeout(() => setTypingName(''), 1800);
      return;
    }
    const concernsSelectedThread = event.thread_id === selectedId || event.thread_ids?.includes(selectedId);
    if (concernsSelectedThread && ['message', 'message_updated', 'message_deleted', 'receipt'].includes(event.type)) {
      loadMessages(selectedId, event.type === 'message').catch(() => {});
    }
  }, [loadMessages, messaging.liveEvent, selectedId]);

  useEffect(() => () => clearTimeout(typingTimerRef.current), []);

  const selectThread = (threadId) => {
    setSelectedId(threadId);
    setReplyingTo(null);
    setEditing(null);
    setComposer('');
  };

  const onComposerChange = (event) => {
    setComposer(event.target.value);
    if (!selectedId) return;
    const now = Date.now();
    if (now - lastTypingRef.current > 1200) {
      lastTypingRef.current = now;
      sendMessageTyping(selectedId).catch(() => {});
    }
  };

  const submitMessage = async () => {
    const text = composer.trim();
    if (!text || !selectedId || sending) return;
    setSending(true);
    setError('');
    try {
      if (editing) await editPlatformMessage(editing.id, text);
      else await sendPlatformMessage(selectedId, text, replyingTo?.id || null);
      setComposer('');
      setReplyingTo(null);
      setEditing(null);
      await loadMessages(selectedId, false);
      await refreshThreads();
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  };

  const beginEdit = (message) => {
    setEditing(message);
    setReplyingTo(null);
    setComposer(message.text);
    inputRef.current?.focus();
  };

  const beginReply = (message) => {
    setReplyingTo(message);
    setEditing(null);
    inputRef.current?.focus();
  };

  const removeMessage = async (message) => {
    if (!window.confirm('Delete this message for everyone?')) return;
    try {
      await deletePlatformMessage(message.id);
      await loadMessages(selectedId, false);
      await refreshThreads();
    } catch (err) {
      setError(err.message);
    }
  };

  const finishDialog = async (thread) => {
    setDialog(null);
    await refreshContacts();
    await refreshThreads();
    selectThread(thread.id);
  };

  if (!messaging.available) {
    return <div className="message-unavailable">Messaging is not available for this profile.</div>;
  }

  return (
    <section className={`messaging-shell ${selectedThread ? 'has-thread' : ''}`} data-testid="messaging-screen">
      <aside className="message-thread-pane">
        <div className="message-list-header">
          <div>
            <h1>Messages</h1>
            <span className={messaging.connected ? 'is-live' : ''}>{messaging.connected ? 'Live' : 'Reconnecting'}</span>
          </div>
          <div>
            <button className="message-icon-btn" onClick={() => setDialog('direct')} aria-label="New message" title="New message"><Plus size={19} /></button>
            <button className="message-icon-btn" onClick={() => setDialog('group')} aria-label="New group" title="New group"><Users size={18} /></button>
          </div>
        </div>
        <label className="message-search">
          <Search size={16} />
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search messages" aria-label="Search messages" />
          {search && <button onClick={() => setSearch('')} aria-label="Clear search"><X size={14} /></button>}
        </label>
        <div className="message-thread-list">
          {filteredThreads.map((thread) => {
            const other = thread.kind === 'direct'
              ? thread.members?.find((member) => member.id !== currentUser.id)
              : null;
            const presence = messaging.contacts.find((contact) => contact.id === other?.id);
            const last = thread.last_message;
            return (
              <button
                key={thread.id}
                className={`message-thread-row ${selectedId === thread.id ? 'is-active' : ''}`}
                onClick={() => selectThread(thread.id)}
                data-testid={`message-thread-${thread.id}`}
              >
                <Avatar name={thread.title} group={thread.kind === 'group'} online={presence?.online} />
                <span className="message-thread-copy">
                  <span className="message-thread-title"><strong>{thread.title}</strong><time>{formatTime(last?.created_at)}</time></span>
                  <span className="message-thread-preview">
                    {last?.sender_id === currentUser.id && <ReceiptTicks receipt={last.receipt} />}
                    <span>{last?.text || (thread.kind === 'group' ? `${thread.members?.length || 0} members` : roleLabel(other))}</span>
                  </span>
                </span>
                {thread.unread_count > 0 && <span className="message-unread-badge">{thread.unread_count > 99 ? '99+' : thread.unread_count}</span>}
              </button>
            );
          })}
          {!filteredThreads.length && (
            <div className="message-list-empty">
              <MessageCircle size={24} />
              <strong>{search ? 'No matching conversations' : 'No messages yet'}</strong>
            </div>
          )}
        </div>
      </aside>

      <main className="message-conversation-pane">
        {selectedThread ? (
          <>
            <header className="message-conversation-header">
              <button className="message-icon-btn message-mobile-back" onClick={() => setSelectedId(null)} aria-label="Back to conversations"><ArrowLeft size={19} /></button>
              <Avatar name={selectedThread.title} group={selectedThread.kind === 'group'} size={38} online={selectedThread.kind === 'direct' && selectedThread.members?.some((member) => messaging.contacts.find((contact) => contact.id === member.id)?.online && member.id !== currentUser.id)} />
              <div>
                <strong>{selectedThread.title}</strong>
                <ContactStatus thread={selectedThread} contacts={messaging.contacts} typing={typingName} />
              </div>
              {selectedThread.kind === 'group' && selectedThread.admin_ids?.includes(currentUser.id) && (
                <button className="message-icon-btn" onClick={() => setDialog('edit')} aria-label="Edit group" title="Edit group"><MoreHorizontal size={19} /></button>
              )}
            </header>

            <div className="message-history" aria-live="polite">
              {loadingMessages && !messages.length ? (
                <div className="message-loading"><div className="spinner" /></div>
              ) : messages.length ? messages.map((message, index) => {
                const own = message.sender_id === currentUser.id;
                const showSender = selectedThread.kind === 'group' && !own && (
                  index === 0 || messages[index - 1]?.sender_id !== message.sender_id
                );
                return (
                  <div key={message.id} className={`message-row ${own ? 'is-own' : ''}`}>
                    <div className={`message-bubble ${message.deleted_at ? 'is-deleted' : ''}`}>
                      {showSender && <span className="message-sender-name">{message.sender_name}</span>}
                      {message.reply_to && (
                        <button className="message-reply-quote" onClick={() => {}} tabIndex={-1}>
                          <strong>{message.reply_to.sender_name}</strong>
                          <span>{message.reply_to.text}</span>
                        </button>
                      )}
                      <p>{message.deleted_at ? 'This message was deleted' : message.text}</p>
                      <span className="message-meta">
                        {message.edited_at && !message.deleted_at ? 'Edited ' : ''}{formatTime(message.created_at)}
                        {own && !message.deleted_at && <ReceiptTicks receipt={message.receipt} />}
                      </span>
                      {!message.deleted_at && (
                        <span className="message-actions">
                          <button onClick={() => beginReply(message)} aria-label="Reply" title="Reply"><Reply size={14} /></button>
                          {own && <button onClick={() => beginEdit(message)} aria-label="Edit" title="Edit"><Pencil size={14} /></button>}
                          {own && <button onClick={() => removeMessage(message)} aria-label="Delete" title="Delete"><Trash2 size={14} /></button>}
                        </span>
                      )}
                    </div>
                  </div>
                );
              }) : (
                <div className="message-history-empty"><MessageCircle size={30} /><strong>{selectedThread.title}</strong></div>
              )}
              {typingName && <div className="message-typing-bubble"><span /><span /><span /></div>}
              <div ref={messagesEndRef} />
            </div>

            {(replyingTo || editing) && (
              <div className="message-composer-context">
                {editing ? <Edit3 size={16} /> : <Reply size={16} />}
                <span><strong>{editing ? 'Editing message' : `Replying to ${replyingTo.sender_name}`}</strong><small>{editing?.text || replyingTo?.text}</small></span>
                <button onClick={() => { setEditing(null); setReplyingTo(null); setComposer(''); }} aria-label="Cancel"><X size={16} /></button>
              </div>
            )}
            <div className="message-composer">
              <textarea
                ref={inputRef}
                value={composer}
                onChange={onComposerChange}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    submitMessage();
                  }
                }}
                placeholder="Message"
                aria-label="Message"
                rows={1}
                maxLength={4000}
              />
              <button className="message-send-btn" onClick={submitMessage} disabled={!composer.trim() || sending} aria-label={editing ? 'Save edit' : 'Send message'} title={editing ? 'Save edit' : 'Send'}>
                {editing ? <Check size={19} /> : <Send size={18} />}
              </button>
            </div>
          </>
        ) : (
          <div className="message-conversation-empty">
            <MessageCircle size={34} />
            <h2>Aaryans messages</h2>
            <p>{messaging.contacts.filter((contact) => !contact.is_self).length} colleagues available</p>
          </div>
        )}
        {error && <div className="message-screen-error" role="alert">{error}<button onClick={() => setError('')} aria-label="Dismiss"><X size={14} /></button></div>}
      </main>

      {dialog && (
        <ComposeDialog
          mode={dialog}
          contacts={messaging.contacts}
          currentUserId={currentUser.id}
          thread={dialog === 'edit' ? selectedThread : null}
          onClose={() => setDialog(null)}
          onCreated={finishDialog}
          onUpdated={finishDialog}
        />
      )}
    </section>
  );
}
