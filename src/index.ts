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
  type GitCommitParams,
} from './types.js';

// ─── Clients ──────────────────────────────────────────────────────────────
const ollamaBaseUrl   = process.env.OLLAMA_BASE_URL    || 'http://localhost:11434';
const routerBaseUrl   = process.env.ROUTER_BASE_URL    || 'http://localhost:4001';
/** Bearer token for router OpenAI-compatible endpoints (Cursor sends this; router does not validate). */
const routerBearer    = process.env.ROUTER_BEARER_TOKEN || 'sk-local-dev-key';

const ollama = new OllamaClient(ollamaBaseUrl);
const router = new RouterClient(routerBaseUrl, routerBearer);

function routerModelForGitTask(task: GitCommitParams['git_task']): string {
  if (task === 'commit_message' || task === 'pr_title') return 'commit';
  return 'auto';
}

function buildGitCommitMessages(params: GitCommitParams): {
  model: string;
  messages: Array<{ role: string; content: string }>;
  temperature: number;
} {
  const task = params.git_task;
  const model = routerModelForGitTask(task);
  const diffBlock = params.diff?.trim() ? `--- Diff ---\n${params.diff.trim()}` : '';
  const contentBlock = params.content?.trim() ? `--- Additional content ---\n${params.content.trim()}` : '';
  const blocks = [diffBlock, contentBlock].filter(Boolean).join('\n\n');
  const ctxLine = params.context?.trim() ? `User context: ${params.context.trim()}\n\n` : '';

  if (task === 'commit_message') {
    const contextLine = params.context ? `\nContext: ${params.context}\n` : '';
    const scopeHint = params.scope
      ? `\nScope hint: "${params.scope}" — use this as the commit scope.`
      : '\nInfer scope from changed file paths (e.g. src/auth/ → auth, router/ → router, src/index.ts → server). Omit scope if truly cross-cutting.';
    const breakingInstructions = params.breaking
      ? '\nThis is a BREAKING CHANGE. You MUST add a blank line after the subject, then a "BREAKING CHANGE: <description>" footer explaining what breaks and how to migrate.'
      : '\nIf the diff clearly removes an export, changes a public API signature, or deletes an endpoint, include a BREAKING CHANGE: footer.';
    const issueFooter = params.issue
      ? `\nInclude this footer line at the end: "Closes #${params.issue}"`
      : '';

    const userPrompt =
      `You are an expert at writing commitizen-compatible conventional git commit messages.\n` +
      `Write a single conventional commit message for the following diff.\n\n` +
      `Format:\n` +
      `  <type>(<scope>): <short description>\n` +
      `  [blank line]\n` +
      `  [optional body: bullet points explaining what and why]\n` +
      `  [blank line]\n` +
      `  [optional footers: BREAKING CHANGE: ..., Closes #N]\n\n` +
      `Types: feat, fix, chore, refactor, docs, test, perf, style, ci, build, revert\n\n` +
      `Rules:\n` +
      `- Subject: 72 chars max, imperative mood, no period at end\n` +
      `- Body: add only if non-obvious; bullet points, wrap at 72 chars\n` +
      `- Output ONLY the commit message. No explanation, no markdown fences.\n` +
      `${scopeHint}\n` +
      `${breakingInstructions}\n` +
      `${issueFooter}\n` +
      `${contextLine}\n` +
      `Diff:\n${params.diff}`;

    return { model, messages: [{ role: 'user', content: userPrompt }], temperature: 0.1 };
  }

  if (task === 'pr_title') {
    const userPrompt =
      `${ctxLine}` +
      `Write a single GitHub pull request title (at most ~72 characters).\n` +
      `Imperative mood, no trailing period, no quotes. Output ONLY the title line.\n\n` +
      `${blocks}`;
    return { model, messages: [{ role: 'user', content: userPrompt }], temperature: 0.15 };
  }

  if (task === 'pr_body') {
    const issueLine = params.issue
      ? `\nInclude a footer line "Closes #${params.issue}" if appropriate, or link the issue in **What**/**Why**.`
      : '';
    const userPrompt =
      `${ctxLine}` +
      `Write a GitHub pull request description in Markdown.\n` +
      `Use these sections: **What**, **Why**, **How tested** (use bullets where helpful).\n` +
      `Do not wrap the whole answer in a markdown fence. No HTML.${issueLine}\n\n` +
      `${blocks}`;
    return { model, messages: [{ role: 'user', content: userPrompt }], temperature: 0.25 };
  }

  if (task === 'gh_command_plan') {
    const instr = params.instruction?.trim() ?? '';
    const userPrompt =
      `${ctxLine}` +
      `Goal (plain English): ${instr}\n\n` +
      `Produce a numbered list of shell commands the user can copy-paste.\n` +
      `Rules:\n` +
      `- Use only standard \`git\` and \`gh\` (GitHub CLI) commands plus common POSIX helpers already implied by git/gh.\n` +
      `- If critical information is missing (branch name, PR number, remote), say exactly what to run first to discover it (e.g. \`git status -sb\`, \`gh pr status\`).\n` +
      `- Clearly mark destructive operations (force-push, hard reset, branch deletion).\n` +
      `- Never invent secrets, tokens, or PATs; never claim commands already ran.\n` +
      `- For opening or updating PRs, prefer \`gh pr create\`, \`gh pr edit\`, \`gh pr view\`, \`gh pr diff\` as appropriate.\n\n` +
      `${blocks}`;
    return { model, messages: [{ role: 'user', content: userPrompt }], temperature: 0.15 };
  }

  // review_thread_reply
  const userPrompt =
    `${ctxLine}` +
    `Draft a concise, professional reply to a code review thread (Markdown OK).\n` +
    `Address each review comment; propose concrete code or test changes where possible; ask a short clarifying question only if needed.\n` +
    `Output only text suitable to paste into GitHub — no preamble like "Here is a reply".\n\n` +
    `${blocks}`;
  return { model, messages: [{ role: 'user', content: userPrompt }], temperature: 0.25 };
}

// ─── Tool definitions ─────────────────────────────────────────────────────

const tools: Tool[] = [
  // ── High-level task tools (use these first — Claude stays thin) ──────────
  {
    name: 'ollama_task',
    description:
      'Delegate a task to a local LLM. The smart router automatically selects the best model ' +
      'based on task content: Rust/code → qwen2.5-coder:14b, summarization/recap/PR text → phi4:latest, ' +
      'architecture/design → deepseek-coder:33b, docs/prose/patents → phi4:latest, quick Q&A → gemma4:latest, ' +
      'general code → qwen2.5-coder:7b. ' +
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
    name: 'ollama_git',
    description:
      'Local LLM helper for git and GitHub CLI workflows via the smart router. ' +
      'Use git_task to choose output: conventional commit message from a diff (default), PR title, PR body, ' +
      'a safe step-by-step git+gh command plan from a stated goal, or a draft reply to a code review thread. ' +
      'Does not run shell commands — you execute suggested git/gh yourself. ' +
      'For commit_message: pass diff (e.g. git diff --staged). For PRs: pass diff and/or pasted gh pr diff / summary in content.',
    inputSchema: {
      type: 'object',
      properties: {
        git_task: {
          type: 'string',
          enum: [
            'commit_message',
            'pr_title',
            'pr_body',
            'gh_command_plan',
            'review_thread_reply',
          ],
          description:
            'commit_message (default): conventional commit from diff. pr_title / pr_body: GitHub PR text. ' +
            'gh_command_plan: numbered git+gh steps (requires instruction). review_thread_reply: draft reply (requires content).',
        },
        diff: {
          type: 'string',
          description: 'Git diff text (staged, branch range, or gh pr diff output).',
        },
        content: {
          type: 'string',
          description:
            'Optional or required context: logs, gh pr view, issue body, review thread + code snippets.',
        },
        instruction: {
          type: 'string',
          description: 'For gh_command_plan: what to accomplish in plain English.',
        },
        context: {
          type: 'string',
          description: 'Optional human note: intent, risk, or links.',
        },
        scope: {
          type: 'string',
          description: 'Optional commit scope hint (commit_message only).',
        },
        breaking: {
          type: 'boolean',
          description: 'commit_message: hint that the change is breaking.',
        },
        issue: {
          type: 'integer',
          description: 'Optional GitHub issue number for Closes #N or PR linking line.',
          minimum: 1,
        },
      },
    },
  },
  {
    name: 'ollama_summarize',
    description:
      'Summarize text, code, or a document using a local LLM. Uses model auto → summarization → phi4:latest ' +
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

      case 'ollama_git': {
        const params = GitCommitSchema.parse(args);
        const { model, messages, temperature } = buildGitCommitMessages(params);
        const response = await router.chat({
          model,
          messages,
          temperature,
        });
        const routed = response.model ?? 'unknown';
        const message = response.choices?.[0]?.message?.content?.trim() ?? '(no response)';
        if (params.git_task === 'commit_message') {
          return text(message);
        }
        return text(`[git_task=${params.git_task} routed:${routed}]\n\n${message}`);
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
