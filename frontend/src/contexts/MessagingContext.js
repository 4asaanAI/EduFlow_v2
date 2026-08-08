import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';

import { getMessagingContacts, getMessagingThreads, subscribeSSE } from '@/lib/api';
import { useUser } from '@/contexts/UserContext';


const MessagingContext = createContext(null);

function canUseMessaging(user) {
  return !!user && (
    user.role === 'owner' ||
    (user.role === 'admin' && ['principal', 'accountant', 'management'].includes(user.sub_category))
  );
}

export function MessagingProvider({ children }) {
  const { currentUser, isAuthenticated } = useUser();
  const available = isAuthenticated && canUseMessaging(currentUser);
  const [threads, setThreads] = useState([]);
  const [contacts, setContacts] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [liveEvent, setLiveEvent] = useState(null);
  const [connected, setConnected] = useState(false);
  const viewRef = useRef({ open: false, threadId: null });
  const audioRef = useRef(null);
  const eventSequenceRef = useRef(0);

  const refreshThreads = useCallback(async () => {
    if (!available) return;
    const response = await getMessagingThreads();
    if (response.success) {
      setThreads(response.data || []);
      setUnreadCount(response.meta?.unread_total || 0);
    }
  }, [available]);

  const refreshContacts = useCallback(async () => {
    if (!available) return;
    const response = await getMessagingContacts();
    if (response.success) setContacts(response.data || []);
  }, [available]);

  const setViewingThread = useCallback((open, threadId = null) => {
    viewRef.current = { open, threadId };
  }, []);

  const playReceivePing = useCallback(() => {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return;
    try {
      const context = audioRef.current || new AudioContextClass();
      audioRef.current = context;
      if (context.state !== 'running') return;
      const gain = context.createGain();
      gain.gain.setValueAtTime(0.0001, context.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.09, context.currentTime + 0.01);
      gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + 0.22);
      gain.connect(context.destination);
      [740, 940].forEach((frequency, index) => {
        const oscillator = context.createOscillator();
        oscillator.frequency.value = frequency;
        oscillator.connect(gain);
        oscillator.start(context.currentTime + index * 0.08);
        oscillator.stop(context.currentTime + 0.14 + index * 0.08);
      });
    } catch {}
  }, []);

  useEffect(() => {
    if (!available) return undefined;
    const unlockAudio = () => {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) return;
      try {
        audioRef.current = audioRef.current || new AudioContextClass();
        audioRef.current.resume?.().catch(() => {});
      } catch {}
    };
    window.addEventListener('pointerdown', unlockAudio, { once: true });
    return () => window.removeEventListener('pointerdown', unlockAudio);
  }, [available]);

  useEffect(() => {
    if (!available) {
      setThreads([]);
      setContacts([]);
      setUnreadCount(0);
      setConnected(false);
      return undefined;
    }

    refreshThreads().catch(() => {});
    refreshContacts().catch(() => {});

    const stop = subscribeSSE('/messaging/stream', (event) => {
      if (!event?.type) return;
      eventSequenceRef.current += 1;
      setLiveEvent({ ...event, sequence: eventSequenceRef.current });

      if (event.type === 'ready') {
        setConnected(true);
        return;
      }
      if (event.type === 'sse_reconnecting') {
        setConnected(false);
        return;
      }
      if (event.type === 'presence') {
        setContacts((current) => current.map((contact) => contact.id === event.user_id
          ? { ...contact, online: event.online, last_seen_at: event.last_seen_at }
          : contact));
        return;
      }
      if (event.type === 'message') {
        const isOpenConversation = viewRef.current.open && viewRef.current.threadId === event.thread_id;
        if (event.message?.sender_id !== currentUser.id && !isOpenConversation) playReceivePing();
        refreshThreads().catch(() => {});
        return;
      }
      if (['thread_created', 'thread_updated', 'message_updated', 'message_deleted', 'receipt'].includes(event.type)) {
        refreshThreads().catch(() => {});
      }
    }, {
      onReconnect: () => {
        refreshThreads().catch(() => {});
        refreshContacts().catch(() => {});
      },
    });

    return () => {
      stop();
      setConnected(false);
    };
  }, [available, currentUser?.id, playReceivePing, refreshContacts, refreshThreads]);

  const value = {
    available,
    connected,
    contacts,
    threads,
    unreadCount,
    liveEvent,
    refreshContacts,
    refreshThreads,
    setViewingThread,
  };

  return <MessagingContext.Provider value={value}>{children}</MessagingContext.Provider>;
}

export function useMessaging() {
  const context = useContext(MessagingContext);
  if (!context) throw new Error('useMessaging must be used within MessagingProvider');
  return context;
}
