// Файл для получения URL аудио произношения слова

import { forwardToPythonApi } from "@/lib/server/pythonApi";

// Динамический рендеринг
export const dynamic = "force-dynamic";

// Обработка GET запроса
export async function GET(request: Request): Promise<Response> {
  const search = new URL(request.url).search;
  return forwardToPythonApi(`/api/v1/dictionary/pronunciation${search}`, { method: "GET" });
}
