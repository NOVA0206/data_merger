import { spawn, execSync } from "node:child_process";
import net from "node:net";
import path from "node:path";

const isWin = process.platform === "win32";
const pythonCmd = process.env.PYTHON || "python";
const nextBin = path.resolve("node_modules/next/dist/bin/next");

function isPortInUse(port, host = "127.0.0.1") {
  return new Promise((resolve) => {
    const socket = net.createConnection({ port, host });
    socket.once("connect", () => {
      socket.destroy();
      resolve(true);
    });
    socket.once("error", () => resolve(false));
  });
}

let apiProc = null;
if (await isPortInUse(8000)) {
  console.log("[dev] Port 8000 is already in use; assuming FastAPI backend is running.");
} else {
  apiProc = spawn(
    pythonCmd,
    ["-m", "uvicorn", "api.index:app", "--host", "127.0.0.1", "--port", "8000"],
    { stdio: "inherit" }
  );
  apiProc.on("exit", (code) => {
    if (code && code !== 0) {
      console.error(`[dev] FastAPI backend exited with code ${code}`);
    }
  });
}

const nextProc = spawn(process.execPath, [nextBin, "dev"], { stdio: "inherit" });

function killTree(proc) {
  if (!proc || proc.killed || !proc.pid) return;
  if (isWin) {
    try {
      execSync(`taskkill /PID ${proc.pid} /T /F`, { stdio: "ignore" });
    } catch {
      // ignore if already exited
    }
  } else {
    proc.kill("SIGTERM");
  }
}

function shutdown(code = 0) {
  killTree(apiProc);
  killTree(nextProc);
  process.exit(code);
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));
nextProc.on("exit", (code) => shutdown(code ?? 0));
