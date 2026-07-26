/**
 * Login form: pick a platform, type a username.
 *
 * MVP trust level only — this proves a username exists on the chosen platform, not that
 * the caller owns it (ADR-0014). The disclaimer stays visible rather than being a tooltip
 * or footnote, because hiding it would be misleading about what "logging in" means here.
 */
import { useState } from 'react';

import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { ApiError } from '@/shared/lib/api-client';
import { cn } from '@/shared/lib/utils';

import type { AuthProvider } from '../api/auth';
import { useLogin } from '../hooks/useAuth';

const PROVIDERS: { value: AuthProvider; label: string }[] = [
  { value: 'lichess', label: 'Lichess' },
  { value: 'chesscom', label: 'Chess.com' },
];

function describeLoginError(error: unknown, provider: AuthProvider, username: string): string {
  const platformLabel = provider === 'lichess' ? 'Lichess' : 'Chess.com';

  if (error instanceof ApiError) {
    if (error.status === 404) {
      return `No ${platformLabel} account named "${username.trim()}".`;
    }
    if (error.status === 502) {
      return `Could not reach ${platformLabel} right now. Try again shortly.`;
    }
  }
  return 'Something went wrong. Please try again.';
}

interface LoginFormProps {
  onSuccess?: () => void;
}

export function LoginForm({ onSuccess }: LoginFormProps) {
  const [provider, setProvider] = useState<AuthProvider>('lichess');
  const [username, setUsername] = useState('');
  const loginMutation = useLogin();

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = username.trim();
    if (!trimmed) {
      return;
    }
    loginMutation.mutate({ provider, username: trimmed }, { onSuccess: () => onSuccess?.() });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="flex gap-2" role="radiogroup" aria-label="Platform">
        {PROVIDERS.map((option) => (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={provider === option.value}
            onClick={() => setProvider(option.value)}
            className={cn(
              'flex-1 rounded-md border px-3 py-2 text-sm font-medium transition-colors',
              provider === option.value
                ? 'border-primary bg-primary text-primary-foreground'
                : 'border-input bg-background hover:bg-accent',
            )}
          >
            {option.label}
          </button>
        ))}
      </div>

      <div className="space-y-1">
        <label htmlFor="username" className="text-sm font-medium">
          {provider === 'lichess' ? 'Lichess' : 'Chess.com'} username
        </label>
        <Input
          id="username"
          name="username"
          autoComplete="username"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          placeholder="e.g. DrNykterstein"
          disabled={loginMutation.isPending}
        />
      </div>

      {loginMutation.isError && (
        <p className="text-sm text-destructive">
          {describeLoginError(loginMutation.error, provider, username)}
        </p>
      )}

      <Button
        type="submit"
        className="w-full"
        disabled={loginMutation.isPending || !username.trim()}
      >
        {loginMutation.isPending
          ? 'Checking…'
          : `Continue with ${provider === 'lichess' ? 'Lichess' : 'Chess.com'}`}
      </Button>

      <p className="text-xs text-muted-foreground">
        This checks that the username exists on the platform — it does not verify you own the
        account. Do not use this for anything private yet.
      </p>
    </form>
  );
}
