/** Shared display formatting for the analytics dashboard's tables and tiles. */

export function formatPercent(rate: number | null): string {
  return rate === null ? '—' : `${(rate * 100).toFixed(1)}%`;
}

export function formatPoints(value: number | null): string {
  return value === null ? '—' : value.toFixed(1);
}

export function formatWeaknessName(name: string): string {
  return name
    .split('_')
    .map((word) => word[0]?.toUpperCase() + word.slice(1))
    .join(' ');
}
