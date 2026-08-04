/**
 * Public surface of the `reports` feature.
 *
 * Other features import from here, never from internal paths.
 */
export { PersonaReportPanel } from './components/PersonaReportPanel';
export { PersonaSwitcher } from './components/PersonaSwitcher';
export { StoryView } from './components/StoryView';
export {
  useGameReport,
  useGameStory,
  useRegenerateGameReport,
  useRegenerateGameStory,
  reportKeys,
} from './hooks/useReports';
export type { GameReport, PersonaValue, ReportFinding } from './api/reports';
// Exported as a value, not just a type: the pattern-feedback response (Phase 19) embeds
// a report, so its own schema has to compose this one rather than restate its shape.
export { gameReportSchema } from './api/reports';
export { AnalyzingNotice } from './components/AnalyzingNotice';
export { isAnalysisPending } from './lib/pending';
