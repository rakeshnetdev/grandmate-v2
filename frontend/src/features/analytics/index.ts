/**
 * Public surface of the `analytics` feature.
 *
 * Other features import from here, never from internal paths.
 */
export { ProfileDashboard } from './components/ProfileDashboard';
export { useProfileAnalytics, analyticsKeys } from './hooks/useAnalytics';
export type { ProfileAnalytics } from './api/analytics';
