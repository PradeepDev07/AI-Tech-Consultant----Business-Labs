import fs from "fs";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { ApprovalService } from "../../src/approval/approval.service.js";
import { EligibilityService } from "../../src/automation/eligibility.service.js";
import { EmailRepository } from "../../src/email/email.repository.js";
import { ProcessedEmailResult } from "../../src/email/email.types.js";
import { FeedbackRepository } from "../../src/feedback/feedback.repository.js";
import { FeedbackService } from "../../src/feedback/feedback.service.js";

describe("Review Workflow Integration", () => {
  const testStorageDir = "storage/test-reviews";

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

  const createMockEmail = (emailId: string, category: any = "pricing_and_plans"): ProcessedEmailResult => ({
    emailId,
    from: "user@example.com",
    subject: "Pricing inquiry",
    body: "Pricing question body",
    category,
    detectedIntents: [category],
    riskLevel: "low",
    requiresHumanReview: true,
    reviewStatus: "pending",
    draft: "Original generated draft text",
    evidence: [],
    knowledgeStatus: "success",
    autoSendEligible: false,
    consecutiveUnchangedApprovals: 0,
    reasons: ["Pending review"],
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  });

  it("should increment consecutive counter on unchanged approval and save feedback record", () => {
    const feedbackRepo = new FeedbackRepository(testStorageDir, "feedback.json");
    const feedbackService = new FeedbackService(feedbackRepo);
    const eligibilityService = new EligibilityService(testStorageDir, "eligibility.json");
    const emailRepo = new EmailRepository(testStorageDir, "emails.json");
    const approvalService = new ApprovalService(emailRepo, eligibilityService, feedbackService);

    const email = createMockEmail("email_1");
    emailRepo.saveEmail(email);

    const result = approvalService.approveUnchanged("email_1", "reviewer_alice", "Looks great");

    expect(result.email.reviewStatus).toBe("approved_unchanged");
    expect(result.email.requiresHumanReview).toBe(false);
    expect(result.eligibility.consecutiveUnchangedCount).toBe(1);

    // Verify feedback recorded
    const history = feedbackService.listAllReviews();
    expect(history.length).toBe(1);
    expect(history[0].isUnchanged).toBe(true);
    expect(history[0].reviewedBy).toBe("reviewer_alice");
  });

  it("should reset consecutive counter to 0 when draft is edited", () => {
    const feedbackRepo = new FeedbackRepository(testStorageDir, "feedback.json");
    const feedbackService = new FeedbackService(feedbackRepo);
    const eligibilityService = new EligibilityService(testStorageDir, "eligibility.json");
    const emailRepo = new EmailRepository(testStorageDir, "emails.json");
    const approvalService = new ApprovalService(emailRepo, eligibilityService, feedbackService);

    // Seed 5 unchanged approvals
    for (let i = 0; i < 5; i++) {
      eligibilityService.recordReviewEvent("pricing_and_plans", "approved_unchanged");
    }
    expect(eligibilityService.getCategoryState("pricing_and_plans").consecutiveUnchangedCount).toBe(5);

    const email = createMockEmail("email_edit");
    emailRepo.saveEmail(email);

    const result = approvalService.approveEdited(
      "email_edit",
      "Edited draft text with custom discount code",
      "reviewer_bob",
      "Added promotional discount"
    );

    expect(result.email.reviewStatus).toBe("approved_edited");
    expect(result.email.draft).toBe("Edited draft text with custom discount code");
    expect(result.eligibility.consecutiveUnchangedCount).toBe(0); // Reset to 0!
  });

  it("should reset counter to 0 on rejection", () => {
    const feedbackRepo = new FeedbackRepository(testStorageDir, "feedback.json");
    const feedbackService = new FeedbackService(feedbackRepo);
    const eligibilityService = new EligibilityService(testStorageDir, "eligibility.json");
    const emailRepo = new EmailRepository(testStorageDir, "emails.json");
    const approvalService = new ApprovalService(emailRepo, eligibilityService, feedbackService);

    eligibilityService.recordReviewEvent("standard_feature_questions", "approved_unchanged");
    expect(eligibilityService.getCategoryState("standard_feature_questions").consecutiveUnchangedCount).toBe(1);

    const email = createMockEmail("email_rej", "standard_feature_questions");
    emailRepo.saveEmail(email);

    const result = approvalService.rejectDraft(
      "email_rej",
      "reviewer_carol",
      "Inaccurate instructions"
    );

    expect(result.email.reviewStatus).toBe("rejected");
    expect(result.eligibility.consecutiveUnchangedCount).toBe(0);
  });
});
