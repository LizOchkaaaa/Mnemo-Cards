// Файл для получения декомпозиции слова

import { forwardToPythonApi } from "@/lib/server/pythonApi";

// Динамический рендеринг
export const dynamic = "force-dynamic";

// Обработка GET запроса
export async function GET(request: Request): Promise<Response> {
  const { searchParams } = new URL(request.url);
  const word = searchParams.get("word") ?? "";
  const translation = searchParams.get("translation") ?? "";
  const lang = searchParams.get("lang") ?? "";
  let q = `word=${encodeURIComponent(word)}&translation=${encodeURIComponent(translation)}`;
  if (lang.trim()) {
    q += `&lang=${encodeURIComponent(lang.trim())}`;
  }
  return forwardToPythonApi(`/api/v1/dictionary/decompose?${q}`, { method: "GET" });
}
