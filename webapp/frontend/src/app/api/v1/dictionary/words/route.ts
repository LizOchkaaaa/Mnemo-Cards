// Файл для получения списка слов словаря пользователя и добавление новых слов

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

// Обработка GET запроса
export async function GET(request: Request): Promise<Response> {
  return forwardToPythonApi("/api/v1/dictionary/words", { method: "GET" }, getExtraHeaders(request));
}

// Обработка POST запроса
export async function POST(request: Request): Promise<Response> {
  const body = await request.text();
  return forwardToPythonApi("/api/v1/dictionary/words", {
    method: "POST",
    body
  }, getExtraHeaders(request));
}
