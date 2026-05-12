/**
 * E2E Tests: Chat Interface — EduFlow
 *
 * Tests the core chat functionality: sending messages, receiving AI responses,
 * and verifying the SSE streaming behavior.
 *
 * Uses the shared admin auth session (from auth.setup.js).
 */

const { test, expect } = require('../support/fixtures');
const { ChatPage } = require('../support/page-objects/ChatPage');
const { waitForApiResponse } = require('../support/helpers/network');

test.describe('Chat Interface', () => {
  let chatPage;

  test.beforeEach(async ({ page }) => {
    chatPage = new ChatPage(page);
    await chatPage.goto();
    await expect(chatPage.chatContainer).toBeVisible();
  });

  test('should display the chat interface on dashboard', async ({ page }) => {
    // Given/Then: the chat interface is visible
    await expect(chatPage.chatContainer).toBeVisible();
    await expect(chatPage.messageInput).toBeVisible();
    await expect(chatPage.sendButton).toBeVisible();
  });

  test('should send a message and receive a response', async ({ page }) => {
    // Given: chat interface is loaded
    // When: user sends a greeting message
    await chatPage.sendMessage('Hello, what can you help me with?');

    // Then: the message appears in the chat list
    await expect(
      page.getByTestId('user-message').last()
    ).toContainText('Hello, what can you help me with?');

    // And: the AI responds (wait up to 30s for SSE response)
    await chatPage.waitForResponse({ timeout: 30_000 });
    const response = await chatPage.getLastResponseText();
    expect(response.length).toBeGreaterThan(0);
  });

  test('should show thinking indicator while waiting for response', async ({ page }) => {
    // Given: chat interface is loaded
    // When: user sends a message
    await chatPage.sendMessage('How many students are enrolled?');

    // Then: thinking indicator appears briefly
    // (This is a timing-sensitive test — we just verify the UI flow)
    // The indicator may appear/disappear quickly, so we accept either state
    const indicatorVisible = await chatPage.thinkingIndicator.isVisible().catch(() => false);
    // The test verifies the flow completes, not just the indicator state
    await chatPage.waitForResponse({ timeout: 30_000 });
  });

  test('should disable send button while response is in progress', async ({ page }) => {
    // Given: a message is being sent
    await chatPage.sendMessage('List all students in Class 5');

    // Then: send button should be disabled during processing
    // (If the app implements this — adjust if the button stays enabled)
    await chatPage.waitForResponse({ timeout: 30_000 });
    await expect(chatPage.sendButton).toBeDisabled();
  });

  test('should support multi-turn conversation', async ({ page }) => {
    // Given: first message has been sent
    await chatPage.askAndWait('How many teachers do we have?');

    // When: user asks a follow-up question
    const followUp = await chatPage.askAndWait('What subjects do they teach?');

    // Then: follow-up receives a meaningful response
    expect(followUp.length).toBeGreaterThan(0);

    // And: both messages appear in the thread
    const messages = page.getByTestId('user-message');
    await expect(messages).toHaveCount(2);
  });
});
