/**
 * Page Object: ChatPage — EduFlow
 *
 * Encapsulates interactions with the main chat interface (ChatInterface.js).
 * The chat is the primary way users interact with EduFlow.
 */

class ChatPage {
  /**
   * @param {import('@playwright/test').Page} page
   */
  constructor(page) {
    this.page = page;
    // Chat interface locators
    this.chatContainer = page.getByTestId('chat-interface');
    this.messageInput = page.getByTestId('chat-input');
    this.sendButton = page.getByTestId('chat-send');
    this.messageList = page.getByTestId('message-list');
    this.thinkingIndicator = page.getByTestId('thinking-indicator');
    this.toolDashboard = page.getByTestId('tool-dashboard');
  }

  async goto() {
    await this.page.goto('/dashboard');
  }

  /**
   * Type a message and send it.
   * @param {string} message
   */
  async sendMessage(message) {
    await this.messageInput.fill(message);
    await this.sendButton.click();
  }

  /**
   * Wait for the AI to finish thinking and return a response.
   * Polls until the thinking indicator disappears.
   * @param {{ timeout?: number }} options
   */
  async waitForResponse(options = {}) {
    const { timeout = 30_000 } = options;
    // Wait for thinking indicator to appear then disappear
    await this.thinkingIndicator.waitFor({ state: 'visible', timeout: 5_000 }).catch(() => {});
    await this.thinkingIndicator.waitFor({ state: 'hidden', timeout });
  }

  /**
   * Get text of the last AI response message.
   * @returns {Promise<string>}
   */
  async getLastResponseText() {
    const messages = this.messageList.getByTestId('assistant-message');
    const last = messages.last();
    return last.textContent();
  }

  /**
   * Send a message and wait for a response.
   * @param {string} message
   * @returns {Promise<string>} The AI's response text
   */
  async askAndWait(message) {
    await this.sendMessage(message);
    await this.waitForResponse();
    return this.getLastResponseText();
  }
}

module.exports = { ChatPage };
