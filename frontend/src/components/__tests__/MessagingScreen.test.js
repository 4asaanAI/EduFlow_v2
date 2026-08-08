import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';

import MessagingScreen from '../MessagingScreen';
import {
  createMessageGroup,
  getPlatformMessages,
  markMessageThreadRead,
  sendMessageTyping,
  sendPlatformMessage,
} from '../../lib/api';


const mockCurrentUser = { id: 'owner-1', name: 'Aman Litt', role: 'owner', sub_category: 'owner' };
let mockMessaging;

jest.mock('../../contexts/UserContext', () => ({
  useUser: () => ({ currentUser: mockCurrentUser }),
}));

jest.mock('../../contexts/MessagingContext', () => ({
  useMessaging: () => mockMessaging,
}));

jest.mock('../../lib/api', () => ({
  createDirectMessageThread: jest.fn(),
  createMessageGroup: jest.fn(),
  deletePlatformMessage: jest.fn(),
  editPlatformMessage: jest.fn(),
  getPlatformMessages: jest.fn(),
  markMessageThreadRead: jest.fn(),
  sendMessageTyping: jest.fn(),
  sendPlatformMessage: jest.fn(),
  updateMessageGroup: jest.fn(),
}));

const contacts = [
  { id: 'owner-1', name: 'Aman Litt', role: 'owner', sub_category: 'owner', is_self: true, online: true },
  { id: 'principal-1', name: 'Adesh Singh', role: 'admin', sub_category: 'principal', online: true },
  { id: 'accountant-1', name: 'Sonu Ruhal', role: 'admin', sub_category: 'accountant', online: false },
  { id: 'management-1', name: 'Lalit Thomas', role: 'admin', sub_category: 'management', online: false },
];

const directThread = {
  id: 'thread-1',
  kind: 'direct',
  title: 'Adesh Singh',
  member_ids: ['owner-1', 'principal-1'],
  members: [contacts[0], contacts[1]],
  unread_count: 1,
  last_message: {
    id: 'message-1', sender_id: 'principal-1', text: 'Good morning', created_at: '2026-08-08T09:00:00+00:00',
  },
};

beforeEach(() => {
  mockMessaging = {
    available: true,
    connected: true,
    contacts,
    threads: [directThread],
    unreadCount: 1,
    liveEvent: null,
    refreshContacts: jest.fn().mockResolvedValue(undefined),
    refreshThreads: jest.fn().mockResolvedValue(undefined),
    setViewingThread: jest.fn(),
  };
  getPlatformMessages.mockResolvedValue({
    success: true,
    data: [{
      id: 'message-1',
      thread_id: 'thread-1',
      sender_id: 'principal-1',
      sender_name: 'Adesh Singh',
      text: 'Good morning',
      created_at: '2026-08-08T09:00:00+00:00',
      receipt: { status: 'read', read_count: 1, delivered_count: 1, recipient_count: 1 },
    }],
  });
  markMessageThreadRead.mockResolvedValue({ success: true, data: { updated: 1 } });
  sendMessageTyping.mockResolvedValue({ success: true });
  sendPlatformMessage.mockResolvedValue({ success: true, data: { id: 'message-2' } });
  createMessageGroup.mockResolvedValue({ success: true, data: { id: 'group-1', title: 'Leadership' } });
});

test('opens a direct thread, marks it read, and sends a message', async () => {
  render(<MessagingScreen />);

  fireEvent.click(screen.getByTestId('message-thread-thread-1'));
  expect(await screen.findByText('Good morning')).toBeInTheDocument();
  await waitFor(() => expect(markMessageThreadRead).toHaveBeenCalledWith('thread-1'));

  fireEvent.change(screen.getByLabelText('Message'), { target: { value: 'Please share the report.' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send message' }));

  await waitFor(() => expect(sendPlatformMessage).toHaveBeenCalledWith(
    'thread-1', 'Please share the report.', null
  ));
});

test('creates a named group from selected leadership profiles', async () => {
  render(<MessagingScreen />);

  fireEvent.click(screen.getByRole('button', { name: 'New group' }));
  const dialog = screen.getByRole('dialog');
  fireEvent.change(within(dialog).getByLabelText('Group name'), { target: { value: 'Leadership' } });
  fireEvent.click(within(dialog).getByText('Adesh Singh').closest('label').querySelector('input'));
  fireEvent.click(within(dialog).getByText('Sonu Ruhal').closest('label').querySelector('input'));
  fireEvent.click(within(dialog).getByRole('button', { name: 'Create group' }));

  await waitFor(() => expect(createMessageGroup).toHaveBeenCalledWith(
    'Leadership', expect.arrayContaining(['principal-1', 'accountant-1'])
  ));
});
