const defaultBaseUrl = "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export class NidavelirApi {
  constructor(private readonly baseUrl = import.meta.env.VITE_NIDAVELIR_API_URL ?? defaultBaseUrl) {}

  async get<T>(path: string, signal?: AbortSignal): Promise<T> {
    const response = await fetch(new URL(path, this.baseUrl), {
      headers: { Accept: "application/json" },
      signal,
    });

    if (!response.ok) {
      throw new ApiError(`Nidavelir API request failed: ${response.status}`, response.status);
    }

    return response.json() as Promise<T>;
  }
}

export const api = new NidavelirApi();
