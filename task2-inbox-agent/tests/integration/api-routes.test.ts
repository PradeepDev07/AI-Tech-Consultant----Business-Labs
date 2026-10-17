import fs from "fs";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { ApprovalService } from "../../src/approval/approval.service.js";
import { EligibilityService } from "../../src/automation/eligibility.service.js";
import { SafetyPolicyService } from "../../src/automation/safety-policy.js";
import { EmailClassifier } from "../../src/classification/classifier.js";
import { DraftService } from "../../src/drafting/draft.service.js";
import { EmailRepository } from "../../src/email/email.repository.js";
import { EmailService } from "../../src/email/email.service.js";
import { FeedbackRepository } from "../../src/feedback/feedback.repository.js";
import { FeedbackService } from "../../src/feedback/feedback.service.js";
import { KnowledgeBrainClient } from "../../src/knowledge-client/knowledge-client.js";
import { MockModelProvider } from "../../src/providers/model-provider.js";
import { createEmailRouter } from "../../src/routes/email.routes.js";
import { createHealthRouter } from "../../src/routes/health.routes.js";
import {
  createAutomationRouter,
  createReviewRouter,
} from "../../src/routes/review.routes.js";

describe("API Routes & Controller Handlers", () => {
  const testStorageDir = "storage/test-api-handlers";
  let emailService: EmailService;
  let approvalService: ApprovalService;
  let eligibilityService: EligibilityService;
  let feedbackService: FeedbackService;

  beforeAll(() => {
    if (fs.existsSync(testStorageDir)) {
      fs.rmSync(testStorageDir, { recursive: true, force: true });
    }

    const modelProvider = new MockModelProvider();
    const feedbackRepo = new FeedbackRepository(testStorageDir, "feedback.json");
    feedbackService = new FeedbackService(feedbackRepo);
    eligibilityService = new EligibilityService(testStorageDir, "eligibility.json");
    const emailRepo = new EmailRepository(testStorageDir, "emails.json");

    const classifier = new EmailClassifier(modelProvider);
    const draftService = new DraftService(modelProvider, feedbackService);
    const safetyPolicy = new SafetyPolicyService();

    const mockKnowledgeClient = {
      queryKnowledgeBrain: async () => ({
        success: true,
        abstained: false,
        answer: "Here is the verified information.",
        citations: [
          {
            article_id: "art_1",
            article_title: "Test Article",
            source_url: "https://support.brilliantdirectories.com/test",
            excerpt: "Test excerpt",
          },
        ],
      }),
    } as unknown as KnowledgeBrainClient;

    emailService = new EmailService(
      classifier,
      mockKnowledgeClient,
      draftService,
      safetyPolicy,
      eligibilityService,
      emailRepo
    );

    approvalService = new ApprovalService(emailRepo, eligibilityService, feedbackService);
  });

  afterAll(() => {
    if (fs.existsSync(testStorageDir)) {
      fs.rmSync(testStorageDir, { recursive: true, force: true });
    }
  });

  function createMockResponse() {
    const res: any = {
      statusCode: 200,
      jsonData: null,
      status(code: number) {
        this.statusCode = code;
        return this;
      },
      json(data: any) {
        this.jsonData = data;
        return this;
      },
    };
    return res;
  }

  it("GET /health handler should return system health status and configuration", async () => {
    const router = createHealthRouter();
    // Find the GET /health layer
    const routeLayer = router.stack.find((s: any) => s.route?.path === "/health");
    expect(routeLayer).toBeDefined();

    const handler = routeLayer.route.stack[0].handle;
    const req: any = {};
    const res = createMockResponse();

    handler(req, res);

    expect(res.statusCode).toBe(200);
    expect(res.jsonData.status).toBe("ok");
    expect(res.jsonData.service).toBe("task2-inbox-agent");
    expect(res.jsonData.knowledgeBrainUrl).toBeDefined();
  });

  it("POST /api/v1/emails handler should process an inbound email and return 201", async () => {
    const router = createEmailRouter(emailService);
    const routeLayer = router.stack.find(
      (s: any) => s.route?.path === "/" && s.route?.methods?.post
    );
    expect(routeLayer).toBeDefined();

    const handler = routeLayer.route.stack[0].handle;
    const req: any = {
      body: {
        emailId: "test_route_001",
        from: "alice@example.com",
        subject: "Pricing inquiry for Brilliant Directories",
        body: "How much does the monthly subscription cost?",
      },
    };
    const res = createMockResponse();

    await handler(req, res);

    expect(res.statusCode).toBe(201);
    expect(res.jsonData.success).toBe(true);
    expect(res.jsonData.data.emailId).toBe("test_route_001");
    expect(res.jsonData.data.category).toBe("pricing_and_plans");
    expect(res.jsonData.data.reviewStatus).toBe("pending");
  });

  it("GET /api/v1/emails/:emailId handler should fetch processed email by ID", async () => {
    const router = createEmailRouter(emailService);
    const routeLayer = router.stack.find(
      (s: any) => s.route?.path === "/:emailId" && s.route?.methods?.get
    );
    expect(routeLayer).toBeDefined();

    const handler = routeLayer.route.stack[0].handle;
    const req: any = {
      params: { emailId: "test_route_001" },
    };
    const res = createMockResponse();

    handler(req, res);

    expect(res.statusCode).toBe(200);
    expect(res.jsonData.success).toBe(true);
    expect(res.jsonData.data.emailId).toBe("test_route_001");
  });

  it("POST /api/v1/reviews/:emailId/approve handler should approve draft unchanged", async () => {
    const router = createReviewRouter(approvalService, eligibilityService, feedbackService);
    const routeLayer = router.stack.find(
      (s: any) => s.route?.path === "/:emailId/approve" && s.route?.methods?.post
    );
    expect(routeLayer).toBeDefined();

    const handler = routeLayer.route.stack[0].handle;
    const req: any = {
      params: { emailId: "test_route_001" },
      body: { reviewedBy: "reviewer_charlie", reviewerNotes: "Looks good" },
    };
    const res = createMockResponse();

    handler(req, res);

    expect(res.statusCode).toBe(200);
    expect(res.jsonData.success).toBe(true);
    expect(res.jsonData.data.email.reviewStatus).toBe("approved_unchanged");
    expect(res.jsonData.data.eligibility.consecutiveUnchangedCount).toBe(1);
  });

  it("POST /api/v1/reviews/:emailId/edit handler should update draft and reset counter", async () => {
    const router = createReviewRouter(approvalService, eligibilityService, feedbackService);
    const routeLayer = router.stack.find(
      (s: any) => s.route?.path === "/:emailId/edit" && s.route?.methods?.post
    );
    expect(routeLayer).toBeDefined();

    const handler = routeLayer.route.stack[0].handle;
    const req: any = {
      params: { emailId: "test_route_001" },
      body: {
        editedDraft: "Brand new edited draft text",
        reviewedBy: "reviewer_charlie",
        reviewerNotes: "Adjusted tone",
      },
    };
    const res = createMockResponse();

    handler(req, res);

    expect(res.statusCode).toBe(200);
    expect(res.jsonData.success).toBe(true);
    expect(res.jsonData.data.email.reviewStatus).toBe("approved_edited");
    expect(res.jsonData.data.email.draft).toBe("Brand new edited draft text");
    expect(res.jsonData.data.eligibility.consecutiveUnchangedCount).toBe(0); // Reset!
  });

  it("GET /api/v1/automation/eligibility handler should return all category counters", async () => {
    const router = createAutomationRouter(eligibilityService, feedbackService);
    const routeLayer = router.stack.find(
      (s: any) => s.route?.path === "/eligibility" && s.route?.methods?.get
    );
    expect(routeLayer).toBeDefined();

    const handler = routeLayer.route.stack[0].handle;
    const req: any = {};
    const res = createMockResponse();

    handler(req, res);

    expect(res.statusCode).toBe(200);
    expect(res.jsonData.success).toBe(true);
    expect(res.jsonData.data.pricing_and_plans).toBeDefined();
    expect(res.jsonData.data.billing_and_payment_issues).toBeDefined();
  });
});
