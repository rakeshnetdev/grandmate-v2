/**
 * Public surface of the `analytics` feature.
 *
 * Other features import from here, never from internal paths.
 */
export { ProfileDashboard } from './components/ProfileDashboard';
export { useProfileAnalytics, analyticsKeys } from './hooks/useAnalytics';
export type {
  OpeningFamilyPerformance,
  ProfileAnalytics,
  RecurringWeakness,
} from './api/analytics';
