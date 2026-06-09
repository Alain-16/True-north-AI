import { fastapiAuthed } from "@/lib/fastapi";

// BFF panel proxy: forwards an authenticated GET to FastAPI's /panels/* and
// returns the JSON straight through. The browser never holds the access token.
const ALLOWED = new Set(["appointments", "reports", "history", "queue"]);

export async function GET(
  req: Request,
  { params }: { params: Promise<{ panel: string }> },
) {
  const { panel } = await params;

  if (!ALLOWED.has(panel)) {
    return new Response(JSON.stringify({ error: "unknown panel" }), {
      status: 404,
      headers: { "Content-Type": "application/json" },
    });
  }

  const upstream = await fastapiAuthed(req, `/panels/${panel}`);

  if (!upstream.ok) {
    return new Response(
      JSON.stringify({ error: "Panel data is unavailable." }),
      { status: upstream.status || 502, headers: { "Content-Type": "application/json" } },
    );
  }

  return new Response(upstream.body, {
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}
