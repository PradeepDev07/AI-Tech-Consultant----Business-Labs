import { Router } from "express";
import { env } from "../config/env.js";

export function createHealthRouter(): Router {
  const router = Router();

  router.get("/health", (_req, res) => {
    res.json({
      status: "ok",
      service: "task2-inbox-agent",
      environment: env.NODE_ENV,
      modelProvider: env.MODEL_PROVIDER,
      modelName: env.MODEL_NAME,
      knowledgeBrainUrl: env.TASK1_API_BASE_URL,
      timestamp: new Date().toISOString(),
    });
  });

  return router;
}
