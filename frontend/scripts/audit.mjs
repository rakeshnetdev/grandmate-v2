#!/usr/bin/env node
/**
 * Dependency audit with a justified allowlist.
 *
 * `npm audit --audit-level=high` is all-or-nothing: one unavoidable advisory and the gate
 * is either permanently red or has to be deleted. Deleting it is how a project stops
 * noticing real vulnerabilities, so instead each accepted advisory is recorded in
 * `.audit-allowlist.json` with a justification and a review date.
 *
 * The script fails on:
 *   - any high/critical advisory that is not allowlisted
 *   - an allowlist entry past its reviewBy date (an accepted risk must be re-examined,
 *     not accepted forever)
 *
 * It warns on:
 *   - an allowlist entry that no longer matches any advisory, so stale exceptions get
 *     removed rather than accumulating
 *
 * No extra dependency: this parses `npm audit --json` directly.
 */
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const GATED_SEVERITIES = new Set(['high', 'critical']);

function runAudit() {
  try {
    // npm audit exits non-zero when it finds anything, so a throw is expected and the
    // payload we want is on stdout either way.
    return execFileSync('npm', ['audit', '--json'], {
      cwd: FRONTEND_ROOT,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    });
  } catch (error) {
    if (typeof error.stdout === 'string' && error.stdout.length > 0) {
      return error.stdout;
    }
    throw error;
  }
}

/** Extract GHSA identifiers and severity from the `npm audit --json` payload. */
function collectAdvisories(report) {
  const found = new Map();

  for (const vulnerability of Object.values(report.vulnerabilities ?? {})) {
    for (const via of vulnerability.via ?? []) {
      // `via` holds either an advisory object or a package name string (a transitive
      // link in the chain). Only the objects carry advisory detail.
      if (typeof via !== 'object' || !via.url) continue;

      const id = via.url.split('/').pop();
      if (!id?.startsWith('GHSA-')) continue;

      found.set(id, {
        id,
        package: via.name ?? vulnerability.name,
        title: via.title ?? '(no title)',
        severity: via.severity ?? vulnerability.severity,
        url: via.url,
      });
    }
  }

  return [...found.values()];
}

const allowlist = JSON.parse(readFileSync(join(FRONTEND_ROOT, '.audit-allowlist.json'), 'utf8'));
const allowed = new Map(allowlist.allow.map((entry) => [entry.id, entry]));

const advisories = collectAdvisories(JSON.parse(runAudit()));
const gated = advisories.filter((advisory) => GATED_SEVERITIES.has(advisory.severity));

const unexpected = gated.filter((advisory) => !allowed.has(advisory.id));
const seen = new Set(advisories.map((advisory) => advisory.id));

const today = new Date().toISOString().slice(0, 10);
const expired = allowlist.allow.filter((entry) => entry.reviewBy < today);
const stale = allowlist.allow.filter((entry) => !seen.has(entry.id));

for (const advisory of unexpected) {
  console.error(`✗ ${advisory.severity.toUpperCase()} ${advisory.id} in ${advisory.package}`);
  console.error(`  ${advisory.title}`);
  console.error(`  ${advisory.url}`);
  console.error(
    '  Fix it, or add it to .audit-allowlist.json with a justification and a review date.\n',
  );
}

for (const entry of expired) {
  console.error(`✗ Allowlist entry ${entry.id} was due for review on ${entry.reviewBy}.`);
  console.error('  Re-check whether it still applies, then extend or remove it.\n');
}

for (const entry of stale) {
  console.warn(`! Allowlist entry ${entry.id} no longer matches any advisory — remove it.`);
}

if (unexpected.length > 0 || expired.length > 0) {
  process.exit(1);
}

const accepted = gated.length;
console.log(
  accepted > 0
    ? `✓ No unexpected advisories. ${accepted} accepted via .audit-allowlist.json.`
    : '✓ No high or critical advisories.',
);
