import http from "node:http";
import type { Socket } from "node:net";
import { AddressInfo } from "node:net";

/**
 * A pass-through proxy in front of the app that the test can take down.
 *
 * `context.setOffline` does not abort a response that is already streaming, so
 * it cannot simulate a backend that went away mid-stream. Killing the sockets
 * and then answering 503 does exactly what a restarting server does: the
 * EventSource ends up CLOSED, which the browser never retries on its own.
 */
export class AppProxy {
  private readonly server: http.Server;
  private readonly sockets = new Set<Socket>();
  private down = false;

  constructor(private readonly target: URL) {
    this.server = http.createServer((req, res) => this.forward(req, res));
    this.server.on("connection", (socket) => {
      this.sockets.add(socket);
      socket.on("close", () => this.sockets.delete(socket));
    });
  }

  static async start(baseUrl: string): Promise<AppProxy> {
    const proxy = new AppProxy(new URL(baseUrl));
    await new Promise<void>((resolve) => proxy.server.listen(0, "127.0.0.1", resolve));
    return proxy;
  }

  get url(): string {
    const { port } = this.server.address() as AddressInfo;
    return `http://127.0.0.1:${port}`;
  }

  /** Drop every open connection and refuse new ones. */
  stop(): void {
    this.down = true;
    for (const socket of this.sockets) socket.destroy();
  }

  resume(): void {
    this.down = false;
  }

  async close(): Promise<void> {
    for (const socket of this.sockets) socket.destroy();
    await new Promise<void>((resolve) => this.server.close(() => resolve()));
  }

  private forward(req: http.IncomingMessage, res: http.ServerResponse): void {
    if (this.down) {
      res.writeHead(503).end();
      return;
    }

    const upstream = http.request(
      {
        host: this.target.hostname,
        port: this.target.port || 80,
        path: req.url,
        method: req.method,
        headers: { ...req.headers, host: this.target.host },
      },
      (response) => {
        res.writeHead(response.statusCode ?? 502, response.headers);
        res.flushHeaders();
        response.pipe(res);
      },
    );

    upstream.on("error", () => res.destroy());
    req.pipe(upstream);
  }
}
