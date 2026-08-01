/**
 * Public surface of the `learning` feature.
 *
 * Other features import from here, never from internal paths.
 */
export { WeeklyFocusPanel } from './components/WeeklyFocusPanel';
export {
  FOCUS_COUNT,
  paginateFocus,
  rankMotifsToLearn,
  rankOpeningsToLearn,
} from './lib/selection';
export { humaniseMotif, lichessOpeningUrl, lichessPuzzleUrl } from './lib/lichess';
