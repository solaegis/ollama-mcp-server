import { z } from 'zod';

// Ollama API Types
export interface OllamaModel {
  name: string;
  model: string;
  modified_at: string;
  size: number;
  digest: string;
  details: {
    parent_model: string;
    format: string;
    family: string;
    families: string[];
    parameter_size: string;
    quantization_level: string;
  };
}

export interface OllamaModelsResponse {
  models: OllamaModel[];
}

export interface OllamaGenerateRequest {
  model: string;
  prompt: string;
  stream?: boolean;
  options?: Record<string, any>;
  system?: string;
  template?: string;
  context?: number[];
  raw?: boolean;
}

export interface OllamaGenerateResponse {
  model: string;
  created_at: string;
  response: string;
  done: boolean;
  context?: number[];
  total_duration?: number;
  load_duration?: number;
  prompt_eval_count?: number;
  prompt_eval_duration?: number;
  eval_count?: number;
  eval_duration?: number;
}

export interface OllamaChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
  images?: string[];
}

export interface OllamaChatRequest {
  model: string;
  messages: OllamaChatMessage[];
  stream?: boolean;
  options?: Record<string, any>;
}

export interface OllamaChatResponse {
  model: string;
  created_at: string;
  message: OllamaChatMessage;
  done: boolean;
  total_duration?: number;
  load_duration?: number;
  prompt_eval_count?: number;
  prompt_eval_duration?: number;
  eval_count?: number;
  eval_duration?: number;
}

export interface OllamaEmbeddingRequest {
  model: string;
  prompt: string;
  options?: Record<string, any>;
}

export interface OllamaEmbeddingResponse {
  embedding: number[];
}

// Zod Schemas for MCP Tool Inputs
export const ListModelsSchema = z.object({});

export const GenerateSchema = z.object({
  model: z.string().describe('Model name to use (e.g., "llama3.1:8b")'),
  prompt: z.string().describe('The prompt to generate a response for'),
  system: z.string().optional().describe('System message to set context'),
  temperature: z.number().min(0).max(2).optional().describe('Temperature for generation (0-2, default 0.8)'),
  top_p: z.number().min(0).max(1).optional().describe('Top-p sampling (0-1)'),
  top_k: z.number().optional().describe('Top-k sampling'),
  num_predict: z.number().optional().describe('Maximum tokens to generate'),
});

export const ChatSchema = z.object({
  model: z.string().describe('Model name to use (e.g., "llama3.1:8b")'),
  messages: z.array(
    z.object({
      role: z.enum(['system', 'user', 'assistant']).describe('Message role'),
      content: z.string().describe('Message content'),
    })
  ).describe('Array of chat messages'),
  temperature: z.number().min(0).max(2).optional().describe('Temperature for generation (0-2, default 0.8)'),
  top_p: z.number().min(0).max(1).optional().describe('Top-p sampling (0-1)'),
  top_k: z.number().optional().describe('Top-k sampling'),
  num_predict: z.number().optional().describe('Maximum tokens to generate'),
});

export const EmbeddingSchema = z.object({
  model: z.string().describe('Model name to use (e.g., "llama3.1:8b")'),
  prompt: z.string().describe('Text to generate embeddings for'),
});

// ─── High-level task schemas ───────────────────────────────────────────────

export const TaskSchema = z.object({
  task: z.string().describe(
    'The task description in plain English. The router selects the best local model automatically based on content ' +
      '(Rust/code → qwen2.5-coder-14b, summarization → gemma4-27b, architecture → gemma4-27b, docs/prose → llama3.3-70b, quick Q&A → gemma4, general code → qwen2.5-coder-7b).'
  ),
  context: z.string().optional().describe(
    'Optional additional context, e.g. relevant code, file contents, or background information to include.'
  ),
  system: z.string().optional().describe(
    'Optional system prompt override. If omitted a sensible default is used.'
  ),
  temperature: z.number().min(0).max(2).optional().describe(
    'Sampling temperature (default 0.2 for deterministic tasks, 0.7 for creative).'
  ),
});

export const GitCommitSchema = z.object({
  diff: z.string().describe(
    'Output of git diff --staged or git diff HEAD. Paste the full diff text.'
  ),
  context: z.string().optional().describe(
    'Optional brief description of what changed and why, to help produce a better commit message.'
  ),
});

export const SummarizeSchema = z.object({
  content: z.string().describe('The text, code, or document to summarize.'),
  goal: z.string().optional().describe(
    'What the summary is for, e.g. "a PR description", "a changelog entry", "a standup update". ' +
      'Routing uses model auto → gemma4-27b for long-context summarization.'
  ),
});

// Router API types
export interface RouterChatRequest {
  model: string;
  messages: Array<{ role: string; content: string }>;
  temperature?: number;
  stream?: boolean;
}

export interface RouterChatResponse {
  id: string;
  model: string;
  choices: Array<{
    message: { role: string; content: string };
    finish_reason: string;
  }>;
  usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number };
}

export interface RouterRouteResponse {
  model: string;
  reason: string;
  /** Present on router >= git_commit routing; older routers omit this. */
  route_key?: string;
}
