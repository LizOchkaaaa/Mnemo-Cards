// Файл для получения кэшированной мнемоники для слова

import { forwardAuthHeaders, forwardToPythonApi } from "@/lib/server/pythonApi";

// Динамический рендеринг
export const dynamic = "force-dynamic";

// Обработка GET запроса
export async function GET(
  request: Request,
  { params }: { params: Promise<{ word: string }> }
): Promise<Response> {
  const { word } = await params;
  const encodedWord = encodeURIComponent(word);
  const u = new URL(request.url);
  const q = u.searchParams.toString();
  const path = `/api/v1/mnemo/cache/${encodedWord}${q ? `?${q}` : ""}`;
  return forwardToPythonApi(path, {
    method: "GET",
    headers: forwardAuthHeaders(request),
  });
}
