#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  Tool,
} from '@modelcontextprotocol/sdk/types.js';
import { OllamaClient, RouterClient } from './client.js';
import {
  ListModelsSchema,
  GenerateSchema,
  ChatSchema,
  EmbeddingSchema,
  TaskSchema,
  GitCommitSchema,
  SummarizeSchema,
} from './types.js';

// ─── Clients ──────────────────────────────────────────────────────────────
const ollamaBaseUrl   = process.env.OLLAMA_BASE_URL    || 'http://localhost:11434';
const routerBaseUrl   = process.env.ROUTER_BASE_URL    || 'http://localhost:4001';
const litellmKey      = process.env.LITELLM_MASTER_KEY || 'sk-local-dev-key';

const ollama = new OllamaClient(ollamaBaseUrl);
const router = new RouterClient(routerBaseUrl, litellmKey);

// ─── Tool definitions ─────────────────────────────────────────────────────

const tools: Tool[] = [
  // ── High-level task tools (use these first — Claude stays thin) ──────────
  {
    name: 'ollama_task',
    description:
      'Delegate a task to a local LLM. The smart router automatically selects the best model ' +
      'based on task content: Rust/code → qwen2.5-coder-14b, summarization/recap/PR text → gemma4-27b, ' +
      'architecture/design → gemma4-27b, docs/prose/patents → llama3.3-70b, quick Q&A → gemma4, ' +
      'general code → qwen2.5-coder-7b. ' +
      'Use this instead of ollama_chat/ollama_generate whenever possible to save Claude tokens. ' +
      'Provide the full task description and any relevant context in the inputs.',
    inputSchema: {
      type: 'object',
      properties: {
        task: {
          type: 'string',
          description:
            'The task in plain English. Be specific. The router classifies this to pick the right model.',
        },
        context: {
          type: 'string',
          description: 'Optional: relevant code, file contents, or background info to include.',
        },
        system: {
          type: 'string',
          description: 'Optional: system prompt override. A sensible default is used if omitted.',
        },
        temperature: {
          type: 'number',
          description: 'Sampling temperature. Default 0.2 (deterministic). Use 0.7+ for creative tasks.',
          minimum: 0,
          maximum: 2,
        },
      },
      required: ['task'],
    },
  },
  {
    name: 'ollama_git_commit',
    description:
      'Generate a conventional commit message (feat/fix/chore/refactor/docs/test/perf) ' +
      'from a git diff. Uses the smart router (model auto → git_commit → qwen2.5-coder-14b). ' +
      'Returns only the commit message, ready to use. Get the diff with: git diff --staged',
    inputSchema: {
      type: 'object',
      properties: {
        diff: {
          type: 'string',
          description: 'Output of git diff --staged or git diff HEAD.',
        },
        context: {
          type: 'string',
          description: 'Optional: brief description of what changed and why.',
        },
      },
      required: ['diff'],
    },
  },
  {
    name: 'ollama_summarize',
    description:
      'Summarize text, code, or a document using a local LLM. Uses model auto → summarization → gemma4-27b ' +
      '(long context). Good for: PR descriptions, changelog entries, standup updates, doc summaries. ' +
      'Saves Claude tokens on large summarization tasks.',
    inputSchema: {
      type: 'object',
      properties: {
        content: {
          type: 'string',
          description: 'The text, code, or document to summarize.',
        },
        goal: {
          type: 'string',
          description:
            'What the summary is for, e.g. "a PR description", "a changelog entry", "a standup update".',
        },
      },
      required: ['content'],
    },
  },

  // ── Low-level tools (use when you need explicit model control) ───────────
  {
    name: 'ollama_list_models',
    description: 'List all available Ollama models on the local instance. Returns model names, sizes, and metadata.',
    inputSchema: {
      type: 'object',
      properties: {},
    },
  },
  {
    name: 'ollama_generate',
    description:
      'Low-level: generate text with a specific Ollama model. ' +
      'Prefer ollama_task unless you need explicit model control.',
    inputSchema: {
      type: 'object',
      properties: {
        model: { type: 'string', description: 'Model name (e.g. "qwen2.5-coder:7b")' },
        prompt: { type: 'string', description: 'The prompt' },
        system: { type: 'string', description: 'System message' },
        temperature: { type: 'number', minimum: 0, maximum: 2 },
        top_p: { type: 'number', minimum: 0, maximum: 1 },
        top_k: { type: 'number' },
        num_predict: { type: 'number', description: 'Max tokens to generate' },
      },
      required: ['model', 'prompt'],
    },
  },
  {
    name: 'ollama_chat',
    description:
      'Low-level: multi-turn chat with a specific Ollama model. ' +
      'Prefer ollama_task unless you need explicit model control or multi-turn history.',
    inputSchema: {
      type: 'object',
      properties: {
        model: { type: 'string', description: 'Model name' },
        messages: {
          type: 'array',
          description: 'Chat messages',
          items: {
            type: 'object',
            properties: {
              role: { type: 'string', enum: ['system', 'user', 'assistant'] },
              content: { type: 'string' },
            },
            required: ['role', 'content'],
          },
        },
        temperature: { type: 'number', minimum: 0, maximum: 2 },
        top_p: { type: 'number', minimum: 0, maximum: 1 },
        top_k: { type: 'number' },
        num_predict: { type: 'number' },
      },
      required: ['model', 'messages'],
    },
  },
  {
    name: 'ollama_embeddings',
    description: 'Generate embeddings for text using nomic-embed-text. Useful for semantic search.',
    inputSchema: {
      type: 'object',
      properties: {
        model: { type: 'string', description: 'Embedding model name (e.g. "nomic-embed-text")' },
        prompt: { type: 'string', description: 'Text to embed' },
      },
      required: ['model', 'prompt'],
    },
  },
];

// ─── MCP Server ───────────────────────────────────────────────────────────

const server = new Server(
  { name: 'ollama-mcp-server', version: '2.0.0' },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools }));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  const text = (s: string) => ({ content: [{ type: 'text' as const, text: s }] });
  const err  = (s: string) => ({ content: [{ type: 'text' as const, text: `Error: ${s}` }], isError: true });

  try {
    switch (name) {

      // ── High-level tools ──────────────────────────────────────────────────

      case 'ollama_task': {
        const params = TaskSchema.parse(args);

        const userContent = params.context
          ? `${params.task}\n\n--- Context ---\n${params.context}`
          : params.task;

        const systemPrompt = params.system ??
          'You are a precise, expert assistant. Complete the task concisely and correctly. ' +
          'Output only what was asked for — no preamble, no explanation unless asked.';

        const response = await router.chat({
          model: 'auto',
          messages: [
            { role: 'system', content: systemPrompt },
            { role: 'user',   content: userContent },
          ],
          temperature: params.temperature ?? 0.2,
        });

        const routed = response.model ?? 'unknown';
        const content = response.choices?.[0]?.message?.content ?? '(no response)';
        return text(`[routed to: ${routed}]\n\n${content}`);
      }

      case 'ollama_git_commit': {
        const params = GitCommitSchema.parse(args);

        const contextLine = params.context ? `\nContext: ${params.context}\n` : '';
        const prompt =
          `You are an expert at writing conventional git commit messages.\n` +
          `Write a single conventional commit message for the following diff.\n` +
          `Format: <type>(<scope>): <short description>\n\n` +
          `Types: feat, fix, chore, refactor, docs, test, perf, style, ci\n` +
          `Rules:\n` +
          `- Subject line: 72 chars max, imperative mood, no period\n` +
          `- If the change is substantial, add a blank line then bullet-point body\n` +
          `- Output ONLY the commit message. No explanation, no markdown fences.\n` +
          `${contextLine}\n` +
          `Diff:\n${params.diff}`;

        const response = await router.chat({
          model: 'auto',
          messages: [{ role: 'user', content: prompt }],
          temperature: 0.1,
        });

        const message = response.choices?.[0]?.message?.content?.trim() ?? '(no response)';
        return text(message);
      }

      case 'ollama_summarize': {
        const params = SummarizeSchema.parse(args);

        const goalLine = params.goal
          ? `Write the summary as: ${params.goal}.`
          : 'Write a clear, concise summary.';

        const prompt =
          `Summarize the following content.\n${goalLine}\n` +
          `Be concise. Capture the key points. Output only the summary.\n\n` +
          `Content:\n${params.content}`;

        const response = await router.chat({
          model: 'auto',
          messages: [{ role: 'user', content: prompt }],
          temperature: 0.3,
        });

        const routed = response.model ?? 'unknown';
        const summary = response.choices?.[0]?.message?.content ?? '(no response)';
        return text(`[routed to: ${routed}]\n\n${summary}`);
      }

      // ── Low-level tools ───────────────────────────────────────────────────

      case 'ollama_list_models': {
        ListModelsSchema.parse(args);
        const response = await ollama.listModels();
        return text(JSON.stringify(response, null, 2));
      }

      case 'ollama_generate': {
        const params = GenerateSchema.parse(args);
        const options: Record<string, any> = {};
        if (params.temperature !== undefined) options.temperature = params.temperature;
        if (params.top_p      !== undefined) options.top_p       = params.top_p;
        if (params.top_k      !== undefined) options.top_k       = params.top_k;
        if (params.num_predict !== undefined) options.num_predict = params.num_predict;

        const response = await ollama.generate({
          model: params.model,
          prompt: params.prompt,
          system: params.system,
          options: Object.keys(options).length > 0 ? options : undefined,
        });
        return text(response.response);
      }

      case 'ollama_chat': {
        const params = ChatSchema.parse(args);
        const options: Record<string, any> = {};
        if (params.temperature !== undefined) options.temperature = params.temperature;
        if (params.top_p      !== undefined) options.top_p       = params.top_p;
        if (params.top_k      !== undefined) options.top_k       = params.top_k;
        if (params.num_predict !== undefined) options.num_predict = params.num_predict;

        const response = await ollama.chat({
          model: params.model,
          messages: params.messages,
          options: Object.keys(options).length > 0 ? options : undefined,
        });
        return text(response.message.content);
      }

      case 'ollama_embeddings': {
        const params = EmbeddingSchema.parse(args);
        const response = await ollama.embeddings({ model: params.model, prompt: params.prompt });
        return text(JSON.stringify(response, null, 2));
      }

      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  } catch (error) {
    return err(error instanceof Error ? error.message : String(error));
  }
});

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('Ollama MCP server v2 running on stdio');
}

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});
