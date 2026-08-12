/**
 * R4-5 - "Report a problem", from the screen.
 *
 * The two things worth a test here are both about honesty rather than layout:
 *
 * 1. **A report that was saved but not delivered says so.** The failure this guards
 *    against has happened on this platform twice: the old bulk messaging route recorded
 *    every recipient as "not configured" and returned success, and every staff message
 *    send returned a 500 for a message that had actually been saved. Both told the
 *    person the opposite of what happened. A green tick over "it has not reached Layaa
 *    AI yet" would be the same mistake a third time.
 *
 * 2. **Every profile is offered the button.** Owner down to student. If a future tidy-up
 *    moves it inside "Help & Support", which hides itself for roles with nothing under
 *    it, students and teachers lose it silently.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ReportProblemModal from '../ReportProblemModal';
import { raisePlatformTicket } from '../../lib/api';

jest.mock('../../lib/api', () => ({ raisePlatformTicket: jest.fn() }));

function fill() {
  fireEvent.change(screen.getByLabelText('What is wrong?'), {
    target: { value: 'The fee collection screen will not open' },
  });
}

describe('reporting a problem', () => {
  beforeEach(() => jest.clearAllMocks());

  it('will not send without one line saying what is wrong', async () => {
    render(<ReportProblemModal onClose={() => {}} />);
    fireEvent.click(screen.getByText('Send this report'));
    expect(await screen.findByRole('alert')).toHaveTextContent('Please say in one line what is wrong.');
    expect(raisePlatformTicket).not.toHaveBeenCalled();
  });

  it('sends the screen it was on, so we can open the same page', async () => {
    raisePlatformTicket.mockResolvedValue({ success: true, data: { id: 'abcd1234', delivered: true, message: 'Reported to Layaa AI as ticket 41.' } });
    render(<ReportProblemModal onClose={() => {}} />);
    fill();
    fireEvent.click(screen.getByText('Send this report'));
    await waitFor(() => expect(raisePlatformTicket).toHaveBeenCalled());
    expect(raisePlatformTicket.mock.calls[0][0].app_url).toBe(window.location.href);
  });

  it('shows the reference back, so nothing is reported silently', async () => {
    raisePlatformTicket.mockResolvedValue({ success: true, data: { id: 'abcd1234-rest', delivered: true, message: 'Reported to Layaa AI as ticket 41.' } });
    render(<ReportProblemModal onClose={() => {}} />);
    fill();
    fireEvent.click(screen.getByText('Send this report'));
    expect(await screen.findByText('Reported to Layaa AI as ticket 41.')).toBeInTheDocument();
    expect(screen.getByText('abcd1234')).toBeInTheDocument();
  });

  it('SAYS SO when the report was saved but has not reached Layaa AI', async () => {
    // The important one. Saved-not-sent is a real outcome and must not wear a tick.
    raisePlatformTicket.mockResolvedValue({
      success: true,
      data: {
        id: 'efgh5678', delivered: false,
        message: 'Saved here, but it has not reached Layaa AI yet. Nothing has been lost and it can be sent again.',
      },
    });
    render(<ReportProblemModal onClose={() => {}} />);
    fill();
    fireEvent.click(screen.getByText('Send this report'));
    expect(await screen.findByText(/has not reached Layaa AI yet/)).toBeInTheDocument();
    expect(screen.getByText(/can be sent again/)).toBeInTheDocument();
  });

  it('tells the person when the report could not be saved at all', async () => {
    raisePlatformTicket.mockResolvedValue({ success: false, detail: 'Please say in one line what is wrong.' });
    render(<ReportProblemModal onClose={() => {}} />);
    fill();
    fireEvent.click(screen.getByText('Send this report'));
    expect(await screen.findByRole('alert')).toBeInTheDocument();
  });

  it('offers a picture of the screen, and does not send one nobody asked for', async () => {
    raisePlatformTicket.mockResolvedValue({ success: true, data: { id: 'x', delivered: true, message: 'Reported.' } });
    render(<ReportProblemModal onClose={() => {}} />);
    expect(screen.getByText('Add a picture of this screen')).toBeInTheDocument();
    fill();
    fireEvent.click(screen.getByText('Send this report'));
    await waitFor(() => expect(raisePlatformTicket).toHaveBeenCalled());
    expect(raisePlatformTicket.mock.calls[0][0].screenshot_base64).toBeUndefined();
  });
});
