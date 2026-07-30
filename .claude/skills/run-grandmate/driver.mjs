#!/usr/bin/env node
/**
 * GrandMate browser driver — logs in and drives the workspace UI programmatically.
 *
 * Zero dependencies on purpose. `chromium-cli` is not installed on this machine and
 * neither is the `playwright` npm package (only its *browser* cache is, left behind by
 * earlier work). Rather than add a dependency to the product's package.json just to
 * drive it, this speaks the Chrome DevTools Protocol directly over the WebSocket that
 * Node 22+ ships as a global — so it runs offline against whatever Chrome is already
 * on disk.
 *
 * Usage (from the repo root, with backend + frontend already running):
 *   node .claude/skills/run-grandmate/driver.mjs smoke [--headed]
 *   node .claude/skills/run-grandmate/driver.mjs shot out.png [--tab story] [--game 1]
 *   node .claude/skills/run-grandmate/driver.mjs eval "document.title"
 *
 * Exit code is nonzero when a step fails, so `smoke` works as a CI-style check.
 */
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const FRONTEND = process.env.GRANDMATE_URL ?? "http://localhost:3535";
const USERNAME = process.env.GRANDMATE_USER ?? "DrNykterstein";
const PORT = Number(process.env.GRANDMATE_CDP_PORT ?? 0);

// Chrome for Testing (from Playwright's browser cache) first, then the everyday Chrome
// install. Either works — this only needs a binary that speaks CDP.
const CHROME_CANDIDATES = [
  `${process.env.HOME}/Library/Caches/ms-playwright/chromium-1234/chrome-mac-x64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
];

function findChrome() {
  const found = CHROME_CANDIDATES.find((p) => existsSync(p));
  if (!found) {
    throw new Error(
      `No Chrome binary found. Looked in:\n  ${CHROME_CANDIDATES.join("\n  ")}\n` +
        "Install Google Chrome, or set one of these paths.",
    );
  }
  return found;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Screenshots default into this skill's own (git-ignored) screenshots/ dir so driving
// the app never leaves untracked files lying around the repo root.
const defaultOut = (name) =>
  join(dirname(new URL(import.meta.url).pathname), "screenshots", name);

/** Minimal CDP client: launches Chrome, attaches to one page, sends commands. */
class Browser {
  constructor({ headed = false } = {}) {
    this.headed = headed;
    this.nextId = 1;
    this.pending = new Map();
  }

  async launch() {
    this.profileDir = mkdtempSync(join(tmpdir(), "grandmate-cdp-"));
    const args = [
      // Port 0 = let the OS pick a free one; Chrome writes it to DevToolsActivePort in
      // the profile dir. A fixed port races against a previous run's Chrome that is
      // still shutting down, which surfaces as a baffling "CDP timeout: Page.navigate"
      // against a stale browser.
      `--remote-debugging-port=${PORT}`,
      `--user-data-dir=${this.profileDir}`,
      "--no-first-run",
      "--no-default-browser-check",
      // Keeps rendering deterministic across machines and avoids GPU flakiness.
      "--disable-gpu",
      "--window-size=1440,900",
    ];
    if (!this.headed) args.push("--headless=new");

    this.proc = spawn(findChrome(), args, { stdio: "ignore" });
    this.proc.on("error", (err) => {
      throw err;
    });

    const wsUrl = await this.waitForDebugger();
    this.ws = new WebSocket(wsUrl);
    await new Promise((res, rej) => {
      this.ws.onopen = res;
      this.ws.onerror = () => rej(new Error("CDP websocket failed to open"));
    });
    this.ws.onmessage = (event) => this.onMessage(JSON.parse(event.data));

    const { targetId } = await this.send("Target.createTarget", {
      url: "about:blank",
    });
    const { sessionId } = await this.send("Target.attachToTarget", {
      targetId,
      flatten: true,
    });
    this.sessionId = sessionId;
    await this.send("Page.enable");
    await this.send("Runtime.enable");
  }

  /** Reads the port Chrome actually chose out of the profile dir, then its WS endpoint. */
  async waitForDebugger() {
    const portFile = join(this.profileDir, "DevToolsActivePort");
    for (let i = 0; i < 150; i++) {
      if (existsSync(portFile)) {
        // Two lines: the port, then the browser's websocket path.
        const [port, path] = readFileSync(portFile, "utf8").trim().split("\n");
        if (port && path) return `ws://127.0.0.1:${port}${path}`;
      }
      await sleep(100);
    }
    throw new Error(
      "Chrome never wrote DevToolsActivePort — it failed to start",
    );
  }

  onMessage(msg) {
    if (msg.id && this.pending.has(msg.id)) {
      const { resolve: res, reject } = this.pending.get(msg.id);
      this.pending.delete(msg.id);
      if (msg.error)
        reject(
          new Error(`${msg.error.message} (${JSON.stringify(msg.error.data)})`),
        );
      else res(msg.result);
    }
  }

  send(method, params = {}) {
    const id = this.nextId++;
    const payload = { id, method, params };
    if (this.sessionId) payload.sessionId = this.sessionId;
    this.ws.send(JSON.stringify(payload));
    return new Promise((res, reject) => {
      this.pending.set(id, { resolve: res, reject });
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id);
          reject(new Error(`CDP timeout: ${method}`));
        }
      }, 30000);
    });
  }

  /** Evaluate JS in the page and return its value. Awaits promises. */
  async eval(expression) {
    const { result, exceptionDetails } = await this.send("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
    });
    if (exceptionDetails) {
      throw new Error(
        `Page threw: ${exceptionDetails.text} ${result?.description ?? ""}`,
      );
    }
    return result.value;
  }

  async goto(url) {
    await this.send("Page.navigate", { url });
    for (let i = 0; i < 150; i++) {
      const state = await this.eval("document.readyState");
      if (state === "complete") return;
      await sleep(100);
    }
    throw new Error(`Page never finished loading: ${url}`);
  }

  /** Polls until `predicate` (a JS expression string) is truthy. */
  async waitFor(predicate, { timeout = 20000, label = predicate } = {}) {
    const deadline = Date.now() + timeout;
    while (Date.now() < deadline) {
      if (await this.eval(`Boolean(${predicate})`)) return true;
      await sleep(200);
    }
    throw new Error(`Timed out waiting for: ${label}`);
  }

  /** Clicks the first element matching `selector` whose text contains `text`. */
  async clickText(selector, text) {
    const clicked = await this.eval(`(() => {
      const el = [...document.querySelectorAll(${JSON.stringify(selector)})]
        .find(e => (e.textContent || '').includes(${JSON.stringify(text)}));
      if (!el) return false;
      el.click();
      return true;
    })()`);
    if (!clicked)
      throw new Error(`No ${selector} containing text ${JSON.stringify(text)}`);
  }

  async type(selector, value) {
    // React tracks its own value; setting .value directly is ignored unless the native
    // setter is called and an input event dispatched.
    await this.eval(`(() => {
      const el = document.querySelector(${JSON.stringify(selector)});
      if (!el) throw new Error('no element ' + ${JSON.stringify(selector)});
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype, 'value').set;
      setter.call(el, ${JSON.stringify(value)});
      el.dispatchEvent(new Event('input', { bubbles: true }));
    })()`);
  }

  async screenshot(outPath) {
    const { data } = await this.send("Page.captureScreenshot", {
      format: "png",
    });
    const abs = resolve(outPath);
    mkdirSync(dirname(abs), { recursive: true });
    writeFileSync(abs, Buffer.from(data, "base64"));
    return abs;
  }

  async close() {
    try {
      this.ws?.close();
    } catch {
      /* already gone */
    }
    this.proc?.kill();
  }
}

/** Logs in through the real form and waits for the workspace to render.
 *
 * `/` is NOT the login form — logged out it renders a landing card, and the form lives
 * on `/login`. Going straight to `/login` covers both states: an already-authenticated
 * session redirects itself to the workspace. */
async function login(b) {
  await b.goto(`${FRONTEND}/login`);
  await b.waitFor(
    'document.querySelector("#username") || document.querySelector("[role=\\"tab\\"]")',
    {
      label: "login form or workspace",
    },
  );
  if (await b.eval('Boolean(document.querySelector("#username"))')) {
    await b.type("#username", USERNAME);
    await b.clickText('button[type="submit"]', "Continue with");
  }
  await b.waitFor('document.querySelector("[role=\\"tab\\"]")', {
    label: "workspace tabs (login to complete)",
  });
}

/** Waits out the panel's own loading states so screenshots aren't of spinners. */
async function settle(b) {
  await b
    .waitFor(
      `!/Loading games|Computing\\.\\.\\.|Loading analysis/.test(document.body.innerText)`,
      { label: "game list + dashboard to finish loading", timeout: 30000 },
    )
    .catch(() => {}); // a slow/empty dashboard is not a failure worth aborting on
  await sleep(400);
}

/** Switches the "My games" / "Study games" toggle. Study games live in a separate
 * profile, so a self profile with no imports can still have games to drive here. */
async function selectProfile(b, which) {
  const label = which === "study" ? "Study games" : "My games";
  await b.clickText("button", label);
  await settle(b);
}

/** Selects the Nth game in the left panel, if any games are loaded. */
async function selectGame(b, index = 1) {
  const picked = await b.eval(`(() => {
    const buttons = [...document.querySelectorAll('button')]
      .filter(el => /\\bvs\\b/.test(el.textContent || ''));
    const el = buttons[${index - 1}];
    if (!el) return null;
    el.click();
    return el.textContent.trim();
  })()`);
  if (picked) await sleep(1200); // let the tab's query settle
  return picked;
}

/** Opens a content tab and waits out its work.
 *
 * Analysis and Story are generated on demand by a real LLM call (5-20s), and Moves /
 * Patterns poll until the background Stockfish job lands — so a fixed sleep here
 * screenshots a spinner nearly every time. */
async function openTab(b, label) {
  await b.clickText('[role="tab"]', label);
  await sleep(500);
  await b
    .waitFor(
      `!/Writing the full game story|Generating|Analyzing this game|Loading/.test(document.body.innerText)`,
      { label: `${label} tab content`, timeout: 60000 },
    )
    .catch(() =>
      console.log(`… ${label} still working after 60s — screenshotting anyway`),
    );
  await sleep(400);
}

async function cmdSmoke(b, args) {
  const out = args.out ?? defaultOut("smoke.png");
  console.log(`→ frontend ${FRONTEND}`);
  await login(b);
  await settle(b);
  console.log("✓ logged in, workspace rendered");

  const tabs = await b.eval(
    `[...document.querySelectorAll('[role="tab"]')].map(t => t.textContent.trim())`,
  );
  console.log(`✓ tabs: ${tabs.join(", ")}`);

  // Try the caller's own games; fall back to the study profile, which is where an
  // arbitrary player's imported games land.
  let game = await selectGame(b, 1);
  if (!game && (await b.eval(`/Study games/.test(document.body.innerText)`))) {
    console.log('… no games in "My games" — trying "Study games"');
    await selectProfile(b, "study");
    game = await selectGame(b, 1);
  }

  if (game) {
    console.log(`✓ selected game: ${game}`);
    const gameTabs = await b.eval(
      `[...document.querySelectorAll('[role="tab"]')].map(t => t.textContent.trim())`,
    );
    console.log(`✓ game tabs: ${gameTabs.join(", ")}`);
  } else {
    console.log(
      "… no games in either profile — import some (see SKILL.md) to drive tabs",
    );
  }

  const errors = await b.eval(
    `[...document.querySelectorAll('*')].filter(e =>
       e.children.length === 0 && /Could not load|Something went wrong/.test(e.textContent||'')
     ).map(e => e.textContent.trim())`,
  );
  if (errors.length) console.log(`! visible errors: ${errors.join(" | ")}`);

  const path = await b.screenshot(out);
  console.log(`✓ screenshot: ${path}`);
  return errors.length ? 1 : 0;
}

async function cmdShot(b, args) {
  const out = args._[1] ?? defaultOut("shot.png");
  await login(b);
  await settle(b);
  if (args.profile) await selectProfile(b, args.profile);
  if (args.game) await selectGame(b, Number(args.game));
  if (args.tab) await openTab(b, args.tab);
  if (args.click) {
    // e.g. --click "Generate training plan" — buttons that kick off an LLM call.
    await b.clickText("button", args.click);
    await b
      .waitFor(`!/Generating|Computing/.test(document.body.innerText)`, {
        label: `"${args.click}" to finish`,
        timeout: 90000,
      })
      .catch(() => console.log("… still working, screenshotting anyway"));
    await sleep(500);
  }
  const path = await b.screenshot(out);
  console.log(path);
  return 0;
}

async function cmdEval(b, args) {
  await login(b);
  await settle(b);
  if (args.profile) await selectProfile(b, args.profile);
  if (args.game) await selectGame(b, Number(args.game));
  if (args.tab) await openTab(b, args.tab);
  console.log(
    JSON.stringify(await b.eval(args._[1] ?? "document.title"), null, 2),
  );
  return 0;
}

function parseArgs(argv) {
  const args = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--headed") args.headed = true;
    else if (a.startsWith("--")) args[a.slice(2)] = argv[++i];
    else args._.push(a);
  }
  return args;
}

const args = parseArgs(process.argv.slice(2));
const command = args._[0] ?? "smoke";
const commands = { smoke: cmdSmoke, shot: cmdShot, eval: cmdEval };
if (!commands[command]) {
  console.error(`Unknown command ${command}. Use: smoke | shot | eval`);
  process.exit(2);
}

const browser = new Browser({ headed: Boolean(args.headed) });
let code = 1;
try {
  await browser.launch();
  code = await commands[command](browser, args);
} catch (err) {
  console.error(`✗ ${err.message}`);
  try {
    console.error(
      `  (screenshot of failure: ${await browser.screenshot(defaultOut("fail.png"))})`,
    );
  } catch {
    /* browser may be gone */
  }
  code = 1;
} finally {
  await browser.close();
}
process.exit(code);
