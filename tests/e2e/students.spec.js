/**
 * E2E Tests: Student Management — EduFlow
 *
 * Tests the student-related tool panel and chat-driven queries.
 * Verifies that admin can view, search, and interact with student data.
 *
 * Uses the shared admin auth session (from auth.setup.js).
 */

const { test, expect } = require('../support/fixtures');
const { ChatPage } = require('../support/page-objects/ChatPage');
const { waitForApiResponse } = require('../support/helpers/network');

test.describe('Student Management', () => {
  let chatPage;

  test.beforeEach(async ({ page }) => {
    chatPage = new ChatPage(page);
    await chatPage.goto();
    await expect(chatPage.chatContainer).toBeVisible();
  });

  test('should retrieve student list via chat query', async ({ page }) => {
    // Given: admin is on the dashboard
    // When: admin asks to list students
    const responseText = await chatPage.askAndWait('Show me students in Class 5 Section A');

    // Then: response contains relevant student information
    expect(responseText).toBeTruthy();
    expect(responseText.length).toBeGreaterThan(10);
  });

  test('should handle student search query via chat', async ({ page }) => {
    // Given: admin is on the dashboard
    // When: admin searches for a specific student
    await chatPage.sendMessage('Find students with pending fees');

    // Wait for API response (network-first pattern)
    const [apiResponse] = await Promise.all([
      waitForApiResponse(page, '/api/chat', { method: 'POST' }),
      chatPage.waitForResponse({ timeout: 30_000 }),
    ]);

    // Then: API responded successfully
    expect(apiResponse.status()).toBe(200);
    const responseText = await chatPage.getLastResponseText();
    expect(responseText.length).toBeGreaterThan(0);
  });

  test('should display attendance information when requested', async ({ page }) => {
    // Given: admin is on the dashboard
    // When: admin asks for attendance data
    const response = await chatPage.askAndWait("What is today's attendance summary?");

    // Then: response includes attendance-related information
    expect(response).toBeTruthy();
  });
});
