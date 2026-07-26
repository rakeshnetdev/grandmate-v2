/**
 * Public surface of the `health` feature.
 *
 * Other features import from here, never from internal paths. That keeps a feature free
 * to reorganise its internals without breaking consumers — the rule that makes the
 * feature-driven structure worth having.
 */
export { BackendStatusCard } from './components/BackendStatusCard';
export { useHealth, useReadiness, healthKeys } from './hooks/useHealth';
export type { HealthStatus, ReadinessStatus } from './api/health';
