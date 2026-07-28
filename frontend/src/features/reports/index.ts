/**
 * Public surface of the `reports` feature.
 *
 * Other features import from here, never from internal paths.
 */
export { PersonaReportPanel } from './components/PersonaReportPanel';
export { useGameReport, reportKeys } from './hooks/useReports';
export type { GameReport, PersonaValue, ReportFinding } from './api/reports';
