import { fastapiAuthed } from "@/lib/fastapi";

// BFF chat proxy: attaches the patient's access token and streams FastAPI's
// SSE response straight through to the browser. The browser never touches
// FastAPI directly, and never holds the token.
export async function POST(req: Request) {
  const { message } = await req.json();

  const upstream = await fastapiAuthed(req, "/chat/stream", {
    method: "POST",
    body: JSON.stringify({ message }),
  });

  if (!upstream.ok || !upstream.body) {
    return new Response(
      JSON.stringify({ error: "Chat is unavailable. Please try again." }),
      { status: upstream.status || 502, headers: { "Content-Type": "application/json" } },
    );
  }

  // Pipe the Server-Sent Events stream through unchanged.
  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "X-Accel-Buffering": "no",
    },
  });
}
