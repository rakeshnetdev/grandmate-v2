/**
 * Public surface of the `learning` feature.
 *
 * Other features import from here, never from internal paths.
 */
export { WeeklyFocusPanel } from './components/WeeklyFocusPanel';
export { useCoveredFocus } from './hooks/useCoveredFocus';
export { FOCUS_COUNT, rankMotifsToLearn, rankOpeningsToLearn, splitFocus } from './lib/selection';
export { humaniseMotif, lichessOpeningUrl, lichessPuzzleUrl } from './lib/lichess';
export { motifKey, openingKey } from './lib/covered-storage';
