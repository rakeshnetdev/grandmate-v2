/**
 * Public surface of the `auth` feature.
 *
 * Other features import from here, never from internal paths.
 */
export { LoginForm } from './components/LoginForm';
export { UserMenu } from './components/UserMenu';
export { useCurrentUser, useLogin, useLogout, authKeys } from './hooks/useAuth';
export type { AuthProvider, CurrentUser } from './api/auth';
