/**
 * Public surface of the `chat` feature.
 *
 * Other features import from here, never from internal paths.
 */
export { ChatPanel } from './components/ChatPanel';
export { useThreads, chatKeys } from './hooks/useChat';
export type { ChatThread, ChatMessage, ChatCitation } from './api/chat';
