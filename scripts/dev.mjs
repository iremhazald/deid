import { spawn, execFileSync } from "node:child_process";
import { copyFileSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const envPath = path.join(root, ".env");
const examplePath = path.join(root, ".env.example");
const winPy = path.join(root, ".venv", "Scripts", "python.exe");
const unixPy = path.join(root, ".venv", "bin", "python");
const python = existsSync(winPy) ? winPy : existsSync(unixPy) ? unixPy : "python";
const apiPort = "8000";
const isWindows = process.platform === "win32";

if (!existsSync(envPath) && existsSync(examplePath)) {
  copyFileSync(examplePath, envPath);
  console.log("Created .env from .env.example. Add your own AI_API_KEY if you want deep scan.");
}

if (!existsSync(winPy) && !existsSync(unixPy)) {
  console.warn(
    "No project virtualenv found at .venv. Using system Python. Prefer: python -m venv .venv && .venv/Scripts/python -m pip install -r apps/api/requirements.txt",
  );
}

// Closing a terminal on Windows often leaves uvicorn listening. Free the port first.
freeProjectApiPort(apiPort);

const api = spawn(
  python,
  [
    "-m",
    "uvicorn",
    "app.main:app",
    "--app-dir",
    "apps/api",
    "--reload",
    "--reload-dir",
    path.join(root, "apps", "api"),
    "--port",
    apiPort,
  ],
  { cwd: root, stdio: "inherit", windowsHide: true, detached: false },
);

api.on("error", (error) => {
  console.error("Could not start the scan server:", error.message);
  process.exit(1);
});

let web;
web = await startWebWhenApiReady();

async function startWebWhenApiReady() {
  const ready = await waitForApi(`http://127.0.0.1:${apiPort}/api/health`);
  if (!ready) {
    console.warn("Scan server is still starting; the UI may show a proxy error until it is up.");
  }
  return spawn("npm", ["run", "dev", "--prefix", "apps/web"], {
    cwd: root,
    stdio: "inherit",
    shell: true,
    windowsHide: true,
    detached: false,
  });
}

async function waitForApi(url, timeoutMs = 40_000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(1500) });
      if (response.ok || response.status < 500) return true;
    } catch {
      // Reloader is up before the worker accepts connections.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  return false;
}

function killTree(child) {
  if (!child?.pid) return;
  if (isWindows) {
    try {
      execFileSync("taskkill", ["/PID", String(child.pid), "/T", "/F"], { stdio: "ignore" });
    } catch {
      child.kill();
    }
    return;
  }
  if (!child.killed) child.kill();
}

function pidsListeningOn(port) {
  if (!isWindows) return [];
  try {
    const out = execFileSync("netstat", ["-ano"], { encoding: "utf8" });
    const pids = new Set();
    for (const line of out.split(/\r?\n/)) {
      if (!line.includes("LISTENING")) continue;
      if (!line.includes(`:${port} `) && !line.includes(`:${port}\t`)) continue;
      const pid = Number(line.trim().split(/\s+/).pop());
      if (pid > 0) pids.add(pid);
    }
    return [...pids];
  } catch {
    return [];
  }
}

function commandLineFor(pid) {
  try {
    return execFileSync(
      "powershell",
      [
        "-NoProfile",
        "-Command",
        `(Get-CimInstance Win32_Process -Filter "ProcessId=${pid}").CommandLine`,
      ],
      { encoding: "utf8" },
    ).trim();
  } catch {
    return "";
  }
}

function freeProjectApiPort(port) {
  const pids = pidsListeningOn(port);
  for (const pid of pids) {
    const command = commandLineFor(pid);
    const ours =
      command.includes("uvicorn") ||
      command.includes("app.main:app") ||
      command.includes("apps/api") ||
      command.includes("apps\\api");
    if (!ours) {
      console.error(
        `Port ${port} is already in use by PID ${pid}, which is not this project's scan server.`,
      );
      continue;
    }
    console.log(`Stopping leftover scan server on port ${port} (PID ${pid}).`);
    try {
      execFileSync("taskkill", ["/PID", String(pid), "/T", "/F"], { stdio: "ignore" });
    } catch {
      // Already gone.
    }
  }
}

function shutdown() {
  killTree(api);
  killTree(web);
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
process.on("exit", shutdown);
api.on("exit", (code) => {
  if (code) {
    console.error("Scan server exited. Deep scan cannot detect your API key until it is running.");
    shutdown();
    process.exit(code);
  }
});
if (web) {
  web.on("exit", (code) => {
    if (code) shutdown();
  });
}
