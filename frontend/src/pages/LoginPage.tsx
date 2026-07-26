/**
 * Login page. Redirects home once a session exists, whether that session already existed
 * on load or was just created by the form.
 */
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

import { LoginForm, useCurrentUser } from '@/features/auth';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/shared/components/ui/card';

export function LoginPage() {
  const navigate = useNavigate();
  const { data: user } = useCurrentUser();

  useEffect(() => {
    if (user) {
      navigate('/', { replace: true });
    }
  }, [user, navigate]);

  return (
    <div className="mx-auto max-w-sm">
      <Card>
        <CardHeader>
          <CardTitle>Log in</CardTitle>
          <CardDescription>Use your Lichess or Chess.com account</CardDescription>
        </CardHeader>
        <CardContent>
          <LoginForm onSuccess={() => navigate('/', { replace: true })} />
        </CardContent>
      </Card>
    </div>
  );
}
