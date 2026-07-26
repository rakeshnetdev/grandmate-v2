/**
 * Header auth state: sign-in link when logged out, name and logout when logged in.
 *
 * Lives in the header rather than only on the login page, so auth state is visible from
 * anywhere in the app — the same reason `useCurrentUser` is a single shared query.
 */
import { Link } from 'react-router-dom';

import { Button, buttonVariants } from '@/shared/components/ui/button';

import { useCurrentUser, useLogout } from '../hooks/useAuth';

export function UserMenu() {
  const { data: user, isPending } = useCurrentUser();
  const logoutMutation = useLogout();

  if (isPending) {
    return null;
  }

  if (!user) {
    return (
      <Link to="/login" className={buttonVariants({ size: 'sm' })}>
        Log in
      </Link>
    );
  }

  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="text-muted-foreground">
        {user.username} <span className="text-xs">({user.provider})</span>
      </span>
      <Button
        variant="outline"
        size="sm"
        onClick={() => logoutMutation.mutate()}
        disabled={logoutMutation.isPending}
      >
        Log out
      </Button>
    </div>
  );
}
