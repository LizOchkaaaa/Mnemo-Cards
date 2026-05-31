// Прокси бинарного WAV (espeak-ng) для произношения

import { forwardBinaryGetFromPython } from "@/lib/server/pythonApi";

// Динамический рендеринг
export const dynamic = "force-dynamic";

// Обработка GET запроса
export async function GET(request: Request): Promise<Response> {
  const search = new URL(request.url).search;
  return forwardBinaryGetFromPython(`/api/v1/dictionary/pronunciation/audio${search}`);
}
