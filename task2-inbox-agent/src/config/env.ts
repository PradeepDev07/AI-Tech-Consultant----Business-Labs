import dotenv from "dotenv";
import { z } from "zod";

dotenv.config();

const EnvSchema = z.object({
  PORT: z.coerce.number().default(3001),
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
  TASK1_API_BASE_URL: z.string().url().default("http://localhost:8000"),
  TASK1_API_KEY: z.string().optional(),
  MODEL_PROVIDER: z.enum(["mock", "ollama", "gemini"]).default("mock"),
  MODEL_NAME: z.string().default("mock-inbox-model"),
  OLLAMA_BASE_URL: z.string().url().default("http://localhost:11434"),
  GEMINI_API_KEY: z.string().optional(),
  REQUEST_TIMEOUT_MS: z.coerce.number().default(10000),
  MAX_RETRIES: z.coerce.number().default(3),
  RETRY_BASE_DELAY_MS: z.coerce.number().default(500),
  STORAGE_DIR: z.string().default("storage"),
});

export type EnvConfig = z.infer<typeof EnvSchema>;

export function loadEnv(): EnvConfig {
  const result = EnvSchema.safeParse(process.env);
  if (!result.success) {
    const formatted = result.error.format();
    throw new Error(`Environment validation failed: ${JSON.stringify(formatted)}`);
  }
  return result.data;
}

export const env = loadEnv();
