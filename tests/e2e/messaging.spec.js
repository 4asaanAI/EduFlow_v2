const { test, expect } = require('@playwright/test');


const owner = {
  id: 'owner-1', name: 'Aman Litt', role: 'owner', sub_category: 'owner',
  branch_id: 'branch-joya', initials: 'AL',
};

const contacts = [
  { ...owner, is_self: true, online: true },
  { id: 'principal-1', name: 'Adesh Singh', role: 'admin', sub_category: 'principal', is_self: false, online: true },
  { id: 'accountant-1', name: 'Sonu Ruhal', role: 'admin', sub_category: 'accountant', is_self: false, online: false, last_seen_at: '2026-08-08T18:15:00+05:30' },
  { id: 'management-1', name: 'Lalit Thomas', role: 'admin', sub_category: 'management', is_self: false, online: true },
];

const directThread = {
  id: 'thread-direct', kind: 'direct', title: 'Adesh Singh',
  member_ids: ['owner-1', 'principal-1'], members: [contacts[0], contacts[1]],
  unread_count: 2,
  last_message: { id: 'message-3', sender_id: 'principal-1', text: 'I will share the signed copy shortly.', created_at: '2026-08-08T18:28:00+05:30' },
};

const groupThread = {
  id: 'thread-group', kind: 'group', name: 'School leadership', title: 'School leadership',
  member_ids: contacts.map((contact) => contact.id), members: contacts, admin_ids: ['owner-1'],
  unread_count: 0,
  last_message: {
    id: 'group-message-1', sender_id: 'owner-1', text: 'Please review the agenda before 9 AM.',
    created_at: '2026-08-08T17:45:00+05:30',
    receipt: { status: 'read', delivered_count: 3, read_count: 3, recipient_count: 3 },
  },
};

const directMessages = [
  {
    id: 'message-1', thread_id: 'thread-direct', sender_id: 'owner-1', sender_name: 'Aman Litt',
    text: 'Adesh ji, please confirm the final certificate register.', created_at: '2026-08-08T18:20:00+05:30',
    receipt: { status: 'read', delivered_count: 1, read_count: 1, recipient_count: 1 },
  },
  {
    id: 'message-2', thread_id: 'thread-direct', sender_id: 'principal-1', sender_name: 'Adesh Singh',
    text: 'Confirmed. The register and supporting records are complete.', created_at: '2026-08-08T18:24:00+05:30',
    receipt: { status: 'read', delivered_count: 1, read_count: 1, recipient_count: 1 },
  },
  {
    id: 'message-3', thread_id: 'thread-direct', sender_id: 'principal-1', sender_name: 'Adesh Singh',
    text: 'I will share the signed copy shortly.', created_at: '2026-08-08T18:28:00+05:30',
    receipt: { status: 'delivered', delivered_count: 1, read_count: 0, recipient_count: 1 },
    reply_to: { id: 'message-1', sender_name: 'Aman Litt', text: 'Adesh ji, please confirm the final certificate register.' },
  },
];

async function mockMessagingApi(page) {
  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const json = (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

    if (path === '/api/auth/refresh') {
      return json({ success: true, access_token: 'visual-token', token: 'visual-token', user: owner });
    }
    if (path === '/api/messaging/stream') {
      return route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: `data: ${JSON.stringify({ type: 'ready', user_id: owner.id })}\n\n`,
      });
    }
    if (path === '/api/messaging/contacts') return json({ success: true, data: contacts, meta: { count: 4 } });
    if (path === '/api/messaging/threads') return json({ success: true, data: [directThread, groupThread], meta: { count: 2, unread_total: 2 } });
    if (path === '/api/messaging/threads/thread-direct/messages' && request.method() === 'GET') {
      return json({ success: true, data: directMessages, meta: { count: directMessages.length, has_more: false } });
    }
    if (path === '/api/messaging/threads/thread-direct/read') return json({ success: true, data: { updated: 2 } });
    if (path === '/api/notifications/unread-count') return json({ success: true, data: { unread_count: 0 } });
    if (path === '/api/settings/academic-years/current') return json({ success: true, data: { name: '2026-27' } });
    if (path === '/api/chat/conversations') return json({ success: true, data: [] });
    return json({ success: true, data: [] });
  });
}

test('leadership messaging is usable on desktop and phone', async ({ page }, testInfo) => {
  await mockMessagingApi(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/dashboard?tool=platform-messaging');

  await expect(page.getByTestId('messaging-screen')).toBeVisible();
  await expect(page.getByTestId('message-badge')).toHaveText('2');
  await page.getByTestId('message-thread-thread-direct').click();
  await expect(page.getByRole('main').getByText('I will share the signed copy shortly.', { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('messaging-desktop.png'), fullPage: true });

  await page.setViewportSize({ width: 360, height: 720 });
  await expect(page.getByRole('main').getByText('I will share the signed copy shortly.', { exact: true })).toBeVisible();
  await page.waitForTimeout(350);
  const hiddenSidebarRight = await page.getByTestId('sidebar').evaluate((element) => element.getBoundingClientRect().right);
  expect(hiddenSidebarRight).toBeLessThanOrEqual(1);
  const mobileOverflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(mobileOverflow).toBeLessThanOrEqual(1);
  await page.screenshot({ path: testInfo.outputPath('messaging-mobile.png'), fullPage: true });

  await page.getByRole('button', { name: 'Back to conversations' }).click();
  await expect(page.getByTestId('message-thread-thread-direct')).toBeVisible();
});
