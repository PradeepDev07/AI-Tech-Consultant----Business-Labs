import fs from "fs";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
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

describe("Email Pipeline Integration", () => {
  const testStorageDir = "storage/test-pipeline";

  beforeEach(() => {
    if (fs.existsSync(testStorageDir)) {
      fs.rmSync(testStorageDir, { recursive: true, force: true });
    }
  });

  afterEach(() => {
    if (fs.existsSync(testStorageDir)) {
      fs.rmSync(testStorageDir, { recursive: true, force: true });
    }
  });

  it("should process inbound email through full pipeline and persist result", async () => {
    const modelProvider = new MockModelProvider();
    const feedbackRepo = new FeedbackRepository(testStorageDir, "feedback.json");
    const feedbackService = new FeedbackService(feedbackRepo);
    const eligibilityService = new EligibilityService(testStorageDir, "eligibility.json");
    const emailRepository = new EmailRepository(testStorageDir, "emails.json");
    const classifier = new EmailClassifier(modelProvider);
    const draftService = new DraftService(modelProvider, feedbackService);
    const safetyPolicy = new SafetyPolicyService();

    const mockKnowledgeClient = {
      queryKnowledgeBrain: async () => ({
        success: true,
        abstained: false,
        answer: "Brilliant Directories monthly pricing starts at $145/mo.",
        citations: [
          {
            article_id: "art_price_1",
            article_title: "Pricing Plans",
            source_url: "https://support.brilliantdirectories.com/pricing",
            excerpt: "Plans start at $145/mo.",
          },
        ],
      }),
    } as unknown as KnowledgeBrainClient;

    const emailService = new EmailService(
      classifier,
      mockKnowledgeClient,
      draftService,
      safetyPolicy,
      eligibilityService,
      emailRepository
    );

    const result = await emailService.processEmail({
      from: "customer@example.com",
      subject: "Pricing inquiry for local directory",
      body: "How much does Brilliant Directories cost per month?",
    });

    expect(result.emailId).toBeDefined();
    expect(result.category).toBe("pricing_and_plans");
    expect(result.draft).toContain("Brilliant Directories");
    expect(result.evidence.length).toBe(1);
    expect(result.evidence[0].sourceUrl).toBe("https://support.brilliantdirectories.com/pricing");
    expect(result.requiresHumanReview).toBe(true); // 0 approvals initially
    expect(result.reviewStatus).toBe("pending");

    // Verify persistence
    const saved = emailService.getEmailById(result.emailId);
    expect(saved).toBeDefined();
    expect(saved?.emailId).toBe(result.emailId);
  });
});
