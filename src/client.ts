import {
  OllamaModelsResponse,
  OllamaGenerateRequest,
  OllamaGenerateResponse,
  OllamaChatRequest,
  OllamaChatResponse,
  OllamaEmbeddingRequest,
  OllamaEmbeddingResponse,
  RouterChatRequest,
  RouterChatResponse,
  RouterRouteResponse,
} from './types.js';

export class OllamaClient {
  private baseUrl: string;

  constructor(baseUrl: string = 'http://localhost:11434') {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    method: string = 'GET',
    body?: unknown
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;

    try {
      const response = await fetch(url, {
        method,
        headers: body ? { 'Content-Type': 'application/json' } : {},
        body: body ? JSON.stringify(body) : undefined,
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(
          `Ollama API error (${response.status}): ${errorText || response.statusText}`
        );
      }

      return await response.json() as unknown as T;
    } catch (error) {
      if (error instanceof Error) {
        if (error.message.includes('fetch failed') || error.message.includes('ECONNREFUSED')) {
          throw new Error(
            `Cannot connect to Ollama at ${this.baseUrl}. Ensure Ollama is running with 'ollama serve'.`
          );
        }
        throw error;
      }
      throw new Error('Unknown error occurred while connecting to Ollama');
    }
  }

  async listModels(): Promise<OllamaModelsResponse> {
    return this.request<OllamaModelsResponse>('/api/tags', 'GET');
  }

  async generate(request: OllamaGenerateRequest): Promise<OllamaGenerateResponse> {
    const body = { ...request, stream: false };
    return this.request<OllamaGenerateResponse>('/api/generate', 'POST', body);
  }

  async chat(request: OllamaChatRequest): Promise<OllamaChatResponse> {
    const body = { ...request, stream: false };
    return this.request<OllamaChatResponse>('/api/chat', 'POST', body);
  }

  async embeddings(request: OllamaEmbeddingRequest): Promise<OllamaEmbeddingResponse> {
    return this.request<OllamaEmbeddingResponse>('/api/embeddings', 'POST', request);
  }
}

// ─── Router client — talks to the smart router on port 4001 ───────────────
// Uses the OpenAI-compatible /v1/chat/completions endpoint.
// Send model="auto" to let the router pick the best model for the content.

export class RouterClient {
  private baseUrl: string;
  private bearerToken: string;

  constructor(
    baseUrl: string = 'http://localhost:4001',
    bearerToken: string = 'sk-local-dev-key'
  ) {
    this.baseUrl = baseUrl;
    this.bearerToken = bearerToken;
  }

  private async request<T>(
    endpoint: string,
    body: unknown
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.bearerToken}`,
        },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Router error (${response.status}): ${errorText || response.statusText}`);
      }

      return await response.json() as unknown as T;
    } catch (error) {
      if (error instanceof Error) {
        if (error.message.includes('fetch failed') || error.message.includes('ECONNREFUSED')) {
          throw new Error(
            `Cannot connect to router at ${this.baseUrl}. Is the stack running? Try: task up`
          );
        }
        throw error;
      }
      throw new Error('Unknown error connecting to router');
    }
  }

  /** Send a task using model="auto" — router picks the best model. */
  async chat(request: RouterChatRequest): Promise<RouterChatResponse> {
    return this.request<RouterChatResponse>('/v1/chat/completions', {
      ...request,
      stream: false,
    });
  }

  /** Ask the router which model it would pick for given messages, without making an LLM call. */
  async route(messages: Array<{ role: string; content: string }>): Promise<RouterRouteResponse> {
    const url = `${this.baseUrl}/route`;
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.bearerToken}`,
      },
      body: JSON.stringify({ messages }),
    });
    if (!response.ok) {
      throw new Error(`Router classify error (${response.status})`);
    }
    return await response.json() as RouterRouteResponse;
  }
}
