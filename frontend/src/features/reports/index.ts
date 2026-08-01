/**
 * Public surface of the `reports` feature.
 *
 * Other features import from here, never from internal paths.
 */
export { PersonaReportPanel } from './components/PersonaReportPanel';
export { PersonaSwitcher } from './components/PersonaSwitcher';
export { StoryView } from './components/StoryView';
export { useGameReport, useGameStory, reportKeys } from './hooks/useReports';
export type { GameReport, PersonaValue, ReportFinding } from './api/reports';
export { AnalyzingNotice } from './components/AnalyzingNotice';
export { isAnalysisPending } from './lib/pending';
