import { forwardBinaryPostFromPython } from "@/lib/server/pythonApi";

export const dynamic = "force-dynamic";

export async function POST(request: Request): Promise<Response> {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return new Response(JSON.stringify({ detail: "Error JSON" }), {
      status: 400,
      headers: { "Content-Type": "application/json; charset=utf-8" },
    });
  }

  return forwardBinaryPostFromPython("/api/v1/dictionary/export/docx", body, request);
}
