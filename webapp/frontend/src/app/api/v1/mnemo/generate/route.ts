// Файл для генерации мнемоники

import { forwardAuthHeaders, forwardToPythonApi } from "@/lib/server/pythonApi";

// Динамический рендеринг
export const dynamic = "force-dynamic";

// Обработка POST запроса
export async function POST(request: Request): Promise<Response> {
  const body = await request.text();
  return forwardToPythonApi("/api/v1/mnemo/generate", {
    method: "POST",
    body,
    headers: forwardAuthHeaders(request),
  });
}
