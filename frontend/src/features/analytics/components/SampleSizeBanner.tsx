interface SampleSizeBannerProps {
  gamesIncluded: number;
}

export function SampleSizeBanner({ gamesIncluded }: SampleSizeBannerProps) {
  return (
    <div className="rounded-md border border-yellow-600/40 bg-yellow-600/10 p-3 text-sm text-yellow-800 dark:border-yellow-500/40 dark:text-yellow-400">
      Only {gamesIncluded} analyzed game{gamesIncluded === 1 ? '' : 's'} in this window — trends and
      recurring weaknesses below are shown but not yet confident. Import more games to firm them up.
    </div>
  );
}
