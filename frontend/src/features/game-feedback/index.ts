/**
 * Public surface of the `game-feedback` feature (Phase 19, D-037).
 *
 * Other features import from here, never from internal paths.
 */
export { PatternFeedbackView } from './components/PatternFeedbackView';
export { InsufficientHistoryNotice } from './components/InsufficientHistoryNotice';
export {
  usePatternFeedback,
  useRegeneratePatternFeedback,
  patternFeedbackKeys,
} from './hooks/usePatternFeedback';
export type { PatternFeedback, Band } from './api/patternFeedback';
