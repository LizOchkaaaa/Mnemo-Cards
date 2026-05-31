// Файл запросов от клиента серверу
 
// Базовый URL Python бэкенда ?
export const PYTHON_API_BASE_URL = process.env.PYTHON_API_URL ?? "http://127.0.0.1:8000";
// Таймаут для запросов к Python API (3 минуты)
export const UPSTREAM_TIMEOUT_MS = 180_000;

// Формируем полный URL для запроса к Python API
export function buildUpstreamUrl(path: string): string {
  return `${PYTHON_API_BASE_URL}${path}`;
}

// Пробрасываем заголовок Authorization с входящего запроса для аутентификации пользователя
export function forwardAuthHeaders(request: Request): Record<string, string> {
  const auth = request.headers.get("Authorization");
  return auth ? { Authorization: auth } : {};
}

// Создаём JSON-ответ с заданным HTTP статусом
function jsonResponse(body: unknown, status: number): Response {
  return Response.json(body, { status });
}

// Преобразуем ответ от сервера
async function parseUpstreamBody(response: Response): Promise<unknown> {
  // Получаем MIME тип содержимого ответа
  const contentType = response.headers.get("content-type") ?? "";
  
  // Обработка JSON ответа
  if (contentType.includes("application/json")) {
    try {
      return await response.json();
    } catch {
      return { detail: "Python API returned malformed JSON" };
    }
  }

  // Обработка текстового ответа
  const text = await response.text();
  if (!text) {
    return { detail: "Python API returned an empty response" };
  }
  // Оборачиваем текст в объект
  return { detail: text };
}

// Основная функция перенаправления запросов серверу
export async function forwardToPythonApi(
  path: string,
  init?: RequestInit,
  extraHeaders?: Record<string, string>
): Promise<Response> {
  // Создаём AbortController для возможности отмены запроса по таймауту
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), UPSTREAM_TIMEOUT_MS);
  
  try {
    // Отправляем запрос
    const upstreamResponse = await fetch(buildUpstreamUrl(path), {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
        ...(extraHeaders ?? {})
      },
      cache: "no-store",         // Отключаем кэширование для актуальных данных
      signal: controller.signal  // Привязываем сигнал для отмены
    });

    // Парсим тело ответа
    const payload = await parseUpstreamBody(upstreamResponse);
    
    // Возвращаем ответ клиенту
    return jsonResponse(payload, upstreamResponse.status);
    
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      return jsonResponse(
        { detail: "Python API request timed out" },
        504
      );
    }
    
    // Любые другие ошибки
    return jsonResponse(
      { detail: "Python API is unavailable" },
      503
    );
  } finally {
    // Очищаем таймаут
    clearTimeout(timeoutId);
  }
}

// Передаем GET запросы для бинарных данных
export async function forwardBinaryGetFromPython(
  path: string,
  extraHeaders?: Record<string, string>
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), UPSTREAM_TIMEOUT_MS);
  
  try {
    // Запрашиваем данные
    const upstreamResponse = await fetch(buildUpstreamUrl(path), {
      method: "GET",
      cache: "no-store",
      signal: controller.signal,
      headers: extraHeaders ?? {},
    });
    
    // Определяем тип
    const contentType = upstreamResponse.headers.get("content-type") ?? "application/octet-stream";
    // Получаем байты
    const buf = await upstreamResponse.arrayBuffer();
    
    // Возвращаем бинарный ответ с заголовками для кэширования
    return new Response(buf, {
      status: upstreamResponse.status,
      headers: {
        "Content-Type": contentType,              // Правильный MIME тип
        "Cache-Control": "public, max-age=86400", // Кэшировать на 24 часа
      },
    });
    
  } catch (error) {
    // Обработка ошибок
    if (error instanceof Error && error.name === "AbortError") {
      return new Response("Gateway timeout", { status: 504 });
    }
    return new Response("Upstream unavailable", { status: 503 });
  } finally {
    clearTimeout(timeoutId);
  }
}

// POST с JSON телом: бинарный ответ Python без парсинга в JSON
export async function forwardBinaryPostFromPython(
  path: string,
  bodyJson: unknown,
  request: Request
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), UPSTREAM_TIMEOUT_MS);

  try {
    const upstreamResponse = await fetch(buildUpstreamUrl(path), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...forwardAuthHeaders(request),
      },
      body: JSON.stringify(bodyJson),
      cache: "no-store",
      signal: controller.signal,
    });

    const contentType =
      upstreamResponse.headers.get("content-type") ?? "application/octet-stream";
    const disposition = upstreamResponse.headers.get("content-disposition");
    const buf = await upstreamResponse.arrayBuffer();

    const headersOut = new Headers();
    headersOut.set("Content-Type", contentType);
    if (disposition) headersOut.set("Content-Disposition", disposition);

    return new Response(buf, {
      status: upstreamResponse.status,
      headers: headersOut,
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      return new Response("Gateway timeout", { status: 504 });
    }
    return new Response("Upstream unavailable", { status: 503 });
  } finally {
    clearTimeout(timeoutId);
  }
}