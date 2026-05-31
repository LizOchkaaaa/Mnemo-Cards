// Файл для получения списка слов, у которых есть кэшированная мнемоника

import { forwardAuthHeaders, forwardToPythonApi } from "@/lib/server/pythonApi";

// Динамический рендеринг
export const dynamic = "force-dynamic";

// Обработка GET запроса
export async function GET(request: Request): Promise<Response> {
  return forwardToPythonApi("/api/v1/mnemo/cache", {
    method: "GET",
    headers: forwardAuthHeaders(request),
  });
}
