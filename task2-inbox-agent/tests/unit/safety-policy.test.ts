import { describe, expect, it } from "vitest";
import { CategoryEligibilityState } from "../../src/automation/eligibility.service.js";
import { SafetyPolicyService } from "../../src/automation/safety-policy.js";
import { ClassificationResult } from "../../src/classification/classification.types.js";
import { KnowledgeLookupResult } from "../../src/knowledge-client/knowledge.types.js";

describe("SafetyPolicyService", () => {
  const safetyService = new SafetyPolicyService();

  const mockEligibility = (count: number, isEligible = count >= 20): CategoryEligibilityState => ({
    consecutiveUnchangedCount: count,
    isEligible,
    totalApprovedUnchanged: count,
    totalEdited: 0,
    totalRejected: 0,
    lastUpdated: new Date().toISOString(),
  });

  const validKnowledge: KnowledgeLookupResult = {
    success: true,
    abstained: false,
    answer: "Documentation answer",
    citations: [
      {
        article_id: "art_1",
        article_title: "Title",
        source_url: "https://support.brilliantdirectories.com/art1",
        excerpt: "Excerpt text",
      },
    ],
  };

  it("should approve auto-send when all safety criteria are met (low-risk category, 20+ approvals, grounded knowledge)", () => {
    const classification: ClassificationResult = {
      primaryCategory: "pricing_and_plans",
      detectedIntents: ["pricing_and_plans"],
      riskLevel: "low",
      requiresHumanReview: false,
      reason: "Standard pricing inquiry.",
    };

    const evaluation = safetyService.evaluateSafety({
      category: "pricing_and_plans",
      classification,
      knowledgeResult: validKnowledge,
      eligibility: mockEligibility(20, true),
    });

    expect(evaluation.autoSendEligible).toBe(true);
    expect(evaluation.requiresHumanReview).toBe(false);
  });

  it("should require human review if consecutive count is strictly below 20", () => {
    const classification: ClassificationResult = {
      primaryCategory: "pricing_and_plans",
      detectedIntents: ["pricing_and_plans"],
      riskLevel: "low",
      requiresHumanReview: false,
      reason: "Standard pricing inquiry.",
    };

    const evaluation = safetyService.evaluateSafety({
      category: "pricing_and_plans",
      classification,
      knowledgeResult: validKnowledge,
      eligibility: mockEligibility(19, false),
    });

    expect(evaluation.autoSendEligible).toBe(false);
    expect(evaluation.requiresHumanReview).toBe(true);
    expect(evaluation.reasons.some((r) => r.includes("19/20"))).toBe(true);
  });

  it("should block auto-send for sensitive categories even if consecutive count is 30", () => {
    const classification: ClassificationResult = {
      primaryCategory: "billing_and_payment_issues",
      detectedIntents: ["billing_and_payment_issues"],
      riskLevel: "high",
      requiresHumanReview: true,
      reason: "Billing issue",
    };

    const evaluation = safetyService.evaluateSafety({
      category: "billing_and_payment_issues",
      classification,
      knowledgeResult: validKnowledge,
      eligibility: mockEligibility(30, false),
    });

    expect(evaluation.autoSendEligible).toBe(false);
    expect(evaluation.requiresHumanReview).toBe(true);
  });

  it("should require human review if Task 1 abstains", () => {
    const classification: ClassificationResult = {
      primaryCategory: "pricing_and_plans",
      detectedIntents: ["pricing_and_plans"],
      riskLevel: "low",
      requiresHumanReview: false,
      reason: "Standard pricing inquiry.",
    };

    const abstainedKnowledge: KnowledgeLookupResult = {
      success: true,
      abstained: true,
      abstentionReason: "No relevant articles",
      answer: "I don't know",
      citations: [],
    };

    const evaluation = safetyService.evaluateSafety({
      category: "pricing_and_plans",
      classification,
      knowledgeResult: abstainedKnowledge,
      eligibility: mockEligibility(20, true),
    });

    expect(evaluation.autoSendEligible).toBe(false);
    expect(evaluation.requiresHumanReview).toBe(true);
  });

  it("should require human review if Task 1 Knowledge Brain lookup failed", () => {
    const classification: ClassificationResult = {
      primaryCategory: "pricing_and_plans",
      detectedIntents: ["pricing_and_plans"],
      riskLevel: "low",
      requiresHumanReview: false,
      reason: "Standard pricing inquiry.",
    };

    const failedKnowledge: KnowledgeLookupResult = {
      success: false,
      abstained: true,
      error: "Connection refused",
      citations: [],
    };

    const evaluation = safetyService.evaluateSafety({
      category: "pricing_and_plans",
      classification,
      knowledgeResult: failedKnowledge,
      eligibility: mockEligibility(20, true),
    });

    expect(evaluation.autoSendEligible).toBe(false);
    expect(evaluation.requiresHumanReview).toBe(true);
  });
});
