// Файл для получения списка категорий слов из словаря пользователя

import { forwardToPythonApi } from "@/lib/server/pythonApi";

// Динамический рендеринг
export const dynamic = "force-dynamic";

// Обработка GET запроса
export async function GET(request: Request): Promise<Response> {
  const authorization = request.headers.get("Authorization");
  const extraHeaders: Record<string, string> = {};
  if (authorization) extraHeaders["Authorization"] = authorization;
  return forwardToPythonApi("/api/v1/dictionary/categories", { method: "GET" }, extraHeaders);
}
