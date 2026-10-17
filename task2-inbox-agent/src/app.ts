import cors from "cors";
import express, { Application, Request, Response, NextFunction } from "express";
import { ApprovalService } from "./approval/approval.service.js";
import { EligibilityService } from "./automation/eligibility.service.js";
import { SafetyPolicyService } from "./automation/safety-policy.js";
import { EmailClassifier } from "./classification/classifier.js";
import { env } from "./config/env.js";
import { DraftService } from "./drafting/draft.service.js";
import { EmailRepository } from "./email/email.repository.js";
import { EmailService } from "./email/email.service.js";
import { FeedbackRepository } from "./feedback/feedback.repository.js";
import { FeedbackService } from "./feedback/feedback.service.js";
import { KnowledgeBrainClient } from "./knowledge-client/knowledge-client.js";
import { getConfiguredModelProvider } from "./providers/configured-provider.js";
import { BaseModelProvider } from "./providers/model-provider.js";
import { createEmailRouter } from "./routes/email.routes.js";
import { createHealthRouter } from "./routes/health.routes.js";
import { createProviderRouter } from "./routes/provider.routes.js";
import { createAutomationRouter, createReviewRouter } from "./routes/review.routes.js";

export interface AppDependencies {
  modelProvider?: BaseModelProvider;
  knowledgeClient?: KnowledgeBrainClient;
  feedbackRepository?: FeedbackRepository;
  feedbackService?: FeedbackService;
  eligibilityService?: EligibilityService;
  emailRepository?: EmailRepository;
  classifier?: EmailClassifier;
  draftService?: DraftService;
  safetyPolicy?: SafetyPolicyService;
  emailService?: EmailService;
  approvalService?: ApprovalService;
}

export interface AppInstance {
  app: Application;
  services: {
    modelProvider: BaseModelProvider;
    knowledgeClient: KnowledgeBrainClient;
    feedbackService: FeedbackService;
    eligibilityService: EligibilityService;
    emailRepository: EmailRepository;
    classifier: EmailClassifier;
    draftService: DraftService;
    safetyPolicy: SafetyPolicyService;
    emailService: EmailService;
    approvalService: ApprovalService;
  };
}

export function createApp(deps: AppDependencies = {}): AppInstance {
  const modelProvider = deps.modelProvider || getConfiguredModelProvider();

  const knowledgeClient =
    deps.knowledgeClient ||
    new KnowledgeBrainClient({
      baseUrl: env.TASK1_API_BASE_URL,
      timeoutMs: env.REQUEST_TIMEOUT_MS,
      maxRetries: 3,
    });

  const feedbackRepo = deps.feedbackRepository || new FeedbackRepository();
  const feedbackService = deps.feedbackService || new FeedbackService(feedbackRepo);

  const eligibilityService = deps.eligibilityService || new EligibilityService();
  const emailRepository = deps.emailRepository || new EmailRepository();

  const classifier = deps.classifier || new EmailClassifier(modelProvider);
  const draftService = deps.draftService || new DraftService(modelProvider, feedbackService);
  const safetyPolicy = deps.safetyPolicy || new SafetyPolicyService();

  const emailService =
    deps.emailService ||
    new EmailService(
      classifier,
      knowledgeClient,
      draftService,
      safetyPolicy,
      eligibilityService,
      emailRepository
    );

  const approvalService =
    deps.approvalService ||
    new ApprovalService(emailRepository, eligibilityService, feedbackService);

  const app = express();

  app.use(cors());
  app.use(express.json());

  // Mount routes
  app.use("/", createHealthRouter());
  app.use("/api/v1/emails", createEmailRouter(emailService));
  app.use(
    "/api/v1/reviews",
    createReviewRouter(approvalService, eligibilityService, feedbackService)
  );
  app.use(
    "/api/v1/automation",
    createAutomationRouter(eligibilityService, feedbackService)
  );
  app.use("/api/v1/provider", createProviderRouter());

  // 404 handler
  app.use((_req: Request, res: Response) => {
    res.status(404).json({
      success: false,
      error: "Endpoint not found",
    });
  });

  // Global error handler
  app.use((err: any, _req: Request, res: Response, _next: NextFunction) => {
    console.error("Unhandled error:", err);
    res.status(500).json({
      success: false,
      error: err.message || "Internal server error",
    });
  });

  return {
    app,
    services: {
      modelProvider,
      knowledgeClient,
      feedbackService,
      eligibilityService,
      emailRepository,
      classifier,
      draftService,
      safetyPolicy,
      emailService,
      approvalService,
    },
  };
}
