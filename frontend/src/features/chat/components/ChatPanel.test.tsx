/**
 * ChatPanel tests: empty state, starting a new thread, and sending a message through to
 * a rendered transcript. Generation/grounding correctness is a backend concern
 * (`test_chat_graph.py`, `test_chat_guardrail.py`); this is about the wiring.
 */
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '@/test/render';

import { ChatPanel } from './ChatPanel';

interface RouteHandler {
  status: number;
  body: unknown;
}

/** Handlers may be async, so a test can hold a request open and assert what the UI shows
 *  while it is still in flight. */
function mockFetchRoutes(handlers: Record<string, () => RouteHandler | Promise<RouteHandler>>) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString();
      const parsed = new URL(url, 'http://localhost');
      const key = `${init?.method ?? 'GET'} ${parsed.pathname}`;
      const handler = handlers[key];
      if (!handler) {
        throw new Error(`Unhandled fetch in test: ${key}`);
      }
      const { status, body } = await handler();
      return {
        ok: status < 400,
        status,
        json: () => Promise.resolve(body),
      };
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

const thread = {
  id: 'thread-1',
  profile_id: 'profile-1',
  title: null,
  active_game_id: null,
  created_at: '2026-07-28T00:00:00Z',
  updated_at: '2026-07-28T00:00:00Z',
};

describe('ChatPanel', () => {
  it('prompts to select or start a conversation when there are no threads', async () => {
    mockFetchRoutes({ 'GET /api/v1/chat/threads': () => ({ status: 200, body: [] }) });

    renderWithProviders(<ChatPanel />);

    expect(await screen.findByText('No conversations yet.')).toBeInTheDocument();
    expect(screen.getByText('Select a conversation or start a new one.')).toBeInTheDocument();
  });

  it('starting a new thread shows the composer', async () => {
    mockFetchRoutes({
      'GET /api/v1/chat/threads': () => ({ status: 200, body: [] }),
      'POST /api/v1/chat/threads': () => ({ status: 201, body: thread }),
      'GET /api/v1/chat/threads/thread-1': () => ({
        status: 200,
        body: { thread, messages: [] },
      }),
    });
    const user = userEvent.setup();

    renderWithProviders(<ChatPanel />);
    await user.click(await screen.findByRole('button', { name: 'New chat' }));

    expect(
      await screen.findByPlaceholderText('Ask about a game, an opening, or a tactic…'),
    ).toBeInTheDocument();
  });

  it('sending a message renders the exchange once the turn resolves', async () => {
    let messagesSent = false;
    mockFetchRoutes({
      'GET /api/v1/chat/threads': () => ({ status: 200, body: [] }),
      'POST /api/v1/chat/threads': () => ({ status: 201, body: thread }),
      'GET /api/v1/chat/threads/thread-1': () => ({
        status: 200,
        body: {
          thread,
          messages: messagesSent
            ? [
                { role: 'user', content: 'what is a fork?' },
                { role: 'assistant', content: 'A fork attacks two pieces at once.' },
              ]
            : [],
        },
      }),
      'POST /api/v1/chat/threads/thread-1/messages': () => {
        messagesSent = true;
        return {
          status: 200,
          body: {
            thread,
            answer: 'A fork attacks two pieces at once.',
            citations: [],
            grounded: true,
          },
        };
      },
    });
    const user = userEvent.setup();

    renderWithProviders(<ChatPanel />);
    await user.click(await screen.findByRole('button', { name: 'New chat' }));
    const input = await screen.findByPlaceholderText('Ask about a game, an opening, or a tactic…');
    await user.type(input, 'what is a fork?');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByText('A fork attacks two pieces at once.')).toBeInTheDocument();
    expect(screen.getByText('what is a fork?')).toBeInTheDocument();
  });

  it('shows the question while the turn is still generating', async () => {
    // The transcript comes from the server and only refreshes once the turn resolves, so
    // the composer used to clear on send and leave nothing but "Thinking…" — the question
    // and its answer then appeared together, and sending looked like it had done nothing.
    let releaseTurn = () => {};
    const turnInFlight = new Promise<void>((resolve) => {
      releaseTurn = resolve;
    });
    let messagesSent = false;
    mockFetchRoutes({
      'GET /api/v1/chat/threads': () => ({ status: 200, body: [] }),
      'POST /api/v1/chat/threads': () => ({ status: 201, body: thread }),
      'GET /api/v1/chat/threads/thread-1': () => ({
        status: 200,
        body: {
          thread,
          messages: messagesSent
            ? [
                { role: 'user', content: 'what is a fork?' },
                { role: 'assistant', content: 'A fork attacks two pieces at once.' },
              ]
            : [],
        },
      }),
      'POST /api/v1/chat/threads/thread-1/messages': async () => {
        await turnInFlight;
        messagesSent = true;
        return {
          status: 200,
          body: {
            thread,
            answer: 'A fork attacks two pieces at once.',
            citations: [],
            grounded: true,
          },
        };
      },
    });
    const user = userEvent.setup();

    renderWithProviders(<ChatPanel />);
    await user.click(await screen.findByRole('button', { name: 'New chat' }));
    const input = await screen.findByPlaceholderText('Ask about a game, an opening, or a tactic…');
    await user.type(input, 'what is a fork?');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    // Still generating: the question is on screen alongside the indicator, not after it.
    expect(await screen.findByText('Thinking…')).toBeInTheDocument();
    expect(screen.getByText('what is a fork?')).toBeInTheDocument();

    releaseTurn();

    // And it survives the handover to the server transcript without flickering out: the
    // mutation stays pending until the refetch lands, so there is never a frame with
    // neither the echoed question nor the stored one.
    expect(await screen.findByText('A fork attacks two pieces at once.')).toBeInTheDocument();
    expect(screen.getByText('what is a fork?')).toBeInTheDocument();
  });
});
