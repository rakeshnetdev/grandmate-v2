import { Link } from 'react-router-dom';

import { buttonVariants } from '@/shared/components/ui/button';

export function NotFoundPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold tracking-tight">Page not found</h1>
      <p className="text-muted-foreground">That route does not exist.</p>
      {/* A link styled as a button. Rendering a Link keeps client-side routing intact,
          which wrapping it in a <button> would not. */}
      <Link to="/" className={buttonVariants()}>
        Back to home
      </Link>
    </div>
  );
}
