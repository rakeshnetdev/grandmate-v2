/**
 * Public surface of the `profiles` feature.
 *
 * Other features import from here, never from internal paths.
 */
export { ProfileToggle } from './components/ProfileToggle';
export { useProfiles, profileKeys } from './hooks/useProfiles';
export type { ProfileSummary } from './api/profiles';
