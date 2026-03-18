const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const KEY  = process.env.NEXT_PUBLIC_ADMIN_KEY ?? "";

export async function adminFetch(path: string, init: RequestInit = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Key":  KEY,
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Request failed");
  }
  return res.json();
}

export const api = {
  get:    (path: string)              => adminFetch(path),
  post:   (path: string, body: unknown) => adminFetch(path, { method: "POST",  body: JSON.stringify(body) }),
  patch:  (path: string, body: unknown) => adminFetch(path, { method: "PATCH", body: JSON.stringify(body) }),
  put:    (path: string, body: unknown) => adminFetch(path, { method: "PUT",   body: JSON.stringify(body) }),
  delete: (path: string)              => adminFetch(path, { method: "DELETE" }),
};

export function sseStream(path: string, onLine: (line: string) => void): () => void {
  const url = `${BASE}${path}`;
  const headers = { "X-Admin-Key": KEY };

  let active = true;

  async function connect() {
    while (active) {
      try {
        const res = await fetch(url, { headers });
        if (!res.body) break;
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";

        while (active) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const lines = buf.split("\n");
          buf = lines.pop() ?? "";
          for (const line of lines) {
            if (line.startsWith("data: ")) onLine(line.slice(6));
          }
        }
      } catch {
        if (active) await new Promise(r => setTimeout(r, 2000)); // reconnect
      }
    }
  }

  connect();
  return () => { active = false; };
}
