import { Router, Request, Response } from "express";
import { getProviderManager } from "../providers/model-provider.js";

export function createProviderRouter(): Router {
  const router = Router();
  const manager = getProviderManager();

  const handleGetStatus = async (_req: Request, res: Response) => {
    try {
      const status = await manager.getStatus();
      res.json(status);
    } catch (err: any) {
      res.status(500).json({ error: err.message || "Failed to get provider status" });
    }
  };

  router.get("/", handleGetStatus);
  router.get("/status", handleGetStatus);

  router.post("/select", async (req: Request, res: Response) => {
    try {
      const { provider, model, apiKey, baseUrl } = req.body || {};
      if (!provider) {
        return res.status(400).json({ error: "Missing required parameter 'provider'." });
      }
      const result = await manager.setActiveProvider(provider, {
        model,
        apiKey,
        baseUrl,
      });
      res.json(result);
    } catch (err: any) {
      const msg = err.message || "Provider switch failed";
      if (msg.includes("Invalid provider") || msg.includes("not configured")) {
        return res.status(400).json({ error: msg });
      }
      res.status(503).json({ error: msg });
    }
  });

  router.post("/test", async (req: Request, res: Response) => {
    try {
      const { provider, model, apiKey, baseUrl } = req.body || {};
      if (!provider) {
        return res.status(400).json({ error: "Missing required parameter 'provider'." });
      }
      const result = await manager.testProvider(provider, {
        model,
        apiKey,
        baseUrl,
      });
      res.json(result);
    } catch (err: any) {
      res.status(500).json({ error: err.message || "Provider test failed" });
    }
  });

  return router;
}
