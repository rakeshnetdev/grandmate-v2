/**
 * Public surface of the `training` feature (Phase 15, D-032).
 *
 * Other features import from here, never from internal paths.
 */
export { TrainingPlanPanel } from './components/TrainingPlanPanel';
export { useGenerateTrainingPlan, useTrainingPlan } from './hooks/useTraining';
export type { TrainingRecommendation } from './api/training';
