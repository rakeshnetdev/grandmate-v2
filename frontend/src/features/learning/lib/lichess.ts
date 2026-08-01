/**
 * Deep links into Lichess for practising a specific weakness.
 *
 * Kept out of the component because it is a mapping between two vocabularies — our
 * detector taxonomy (`db/models/patterns.py::TacticalMotifType`) and Lichess's puzzle
 * theme slugs — and a wrong entry sends a learner to the wrong exercise. Every motif in
 * our taxonomy is mapped explicitly; there is no fallback that guesses a slug, because a
 * guessed slug produces a 404 rather than an obviously-missing link.
 */

/** Our motif name → the Lichess puzzle theme slug at `lichess.org/training/{slug}`. */
const MOTIF_TO_LICHESS_THEME: Record<string, string> = {
  fork: 'fork',
  pin: 'pin',
  skewer: 'skewer',
  discovered_attack: 'discoveredAttack',
  double_check: 'doubleCheck',
  back_rank_mate: 'backRankMate',
  smothered_mate: 'smotheredMate',
  hanging_piece: 'hangingPiece',
  // Lichess calls this "Capturing the defender".
  removing_the_defender: 'capturingDefender',
  x_ray: 'xRayAttack',
};

/**
 * Puzzle URL for a motif, or `null` when we have no confident mapping — the caller
 * renders those as plain text rather than a link that would 404.
 */
export function lichessPuzzleUrl(motifName: string): string | null {
  const slug = MOTIF_TO_LICHESS_THEME[motifName];
  return slug ? `https://lichess.org/training/${slug}` : null;
}

/**
 * Opening explorer URL. Lichess addresses openings by name with underscores for spaces,
 * e.g. `lichess.org/opening/Sicilian_Defense`. Family names come from the Lichess
 * openings dataset we already match against (ADR-0009), so they are the same vocabulary.
 */
export function lichessOpeningUrl(family: string): string {
  return `https://lichess.org/opening/${encodeURIComponent(family.trim().replace(/\s+/g, '_'))}`;
}

/** `back_rank_mate` → `Back rank mate`, for display only. */
export function humaniseMotif(motifName: string): string {
  const spaced = motifName.replace(/_/g, ' ');
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}
