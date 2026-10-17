import { createApp } from "./app.js";
import { env } from "./config/env.js";

const { app } = createApp();

const server = app.listen(env.PORT, () => {
  console.log(`====================================================`);
  console.log(`🚀 Task 2 Inbox Agent running on http://localhost:${env.PORT}`);
  console.log(`🔧 Model Provider: ${env.MODEL_PROVIDER}`);
  if (env.MODEL_PROVIDER === "ollama") {
    console.log(`🧠 Ollama Model: ${env.MODEL_NAME} at ${env.OLLAMA_BASE_URL}`);
  }
  console.log(`🔗 Task 1 Knowledge Brain: ${env.TASK1_API_BASE_URL}`);
  console.log(`====================================================`);
});

process.on("SIGINT", () => {
  console.log("\nShutting down Task 2 Inbox Agent...");
  server.close(() => {
    process.exit(0);
  });
});

process.on("SIGTERM", () => {
  console.log("\nTerminating Task 2 Inbox Agent...");
  server.close(() => {
    process.exit(0);
  });
});
