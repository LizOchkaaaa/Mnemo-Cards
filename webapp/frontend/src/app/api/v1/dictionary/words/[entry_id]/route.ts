// Файл для обновления и удаления слов

import { forwardToPythonApi } from "@/lib/server/pythonApi";

// Динамический рендеринг
export const dynamic = "force-dynamic";

// Авторизация
function getExtraHeaders(request: Request): Record<string, string> {
  const authorization = request.headers.get("Authorization");
  const out: Record<string, string> = {};
  if (authorization) out["Authorization"] = authorization;
  return out;
}

// Обработка PATCH запроса
export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ entry_id: string }> }
): Promise<Response> {
  const { entry_id } = await params;
  const body = await request.text();
  return forwardToPythonApi(`/api/v1/dictionary/words/${encodeURIComponent(entry_id)}`, {
    method: "PATCH",
    body
  }, getExtraHeaders(request));
}

// Обработка DELETE запроса
export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ entry_id: string }> }
): Promise<Response> {
  const { entry_id } = await params;
  return forwardToPythonApi(`/api/v1/dictionary/words/${encodeURIComponent(entry_id)}`, {
    method: "DELETE"
  }, getExtraHeaders(request));
}
