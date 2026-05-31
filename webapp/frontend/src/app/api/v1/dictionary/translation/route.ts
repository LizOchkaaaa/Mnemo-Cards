// Прокси перевода слова (MyMemory: query word, source_lang, target_lang)

import { forwardToPythonApi } from "@/lib/server/pythonApi";

// Динамический рендеринг
export const dynamic = "force-dynamic";

// Обработка GET запроса
export async function GET(request: Request): Promise<Response> {
  const { search } = new URL(request.url);
  return forwardToPythonApi(`/api/v1/dictionary/translation${search}`, { method: "GET" });
}
