/**
 * "Show engine analysis" switch — sits beside the My games / Study games toggle and
 * controls whether the engine-detail tabs ("Moves", "Patterns") are offered at all.
 *
 * A switch rather than a button: this is one setting that is either on or off and takes
 * effect immediately, not a choice between two named things the way `ProfileToggle` is.
 */
import { Switch } from '@/shared/components/ui/switch';

interface EngineAnalysisToggleProps {
  shown: boolean;
  onToggle: () => void;
}

export function EngineAnalysisToggle({ shown, onToggle }: EngineAnalysisToggleProps) {
  return <Switch checked={shown} onCheckedChange={onToggle} label="Show engine analysis" />;
}
