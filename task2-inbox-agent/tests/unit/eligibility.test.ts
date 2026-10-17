import fs from "fs";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { EligibilityService } from "../../src/automation/eligibility.service.js";

describe("EligibilityService", () => {
  const testStorageDir = "storage/test-eligibility";
  const testFileName = "eligibility.json";

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

  it("should initialize all categories with 0 consecutive approvals and ineligible status", () => {
    const service = new EligibilityService(testStorageDir, testFileName);
    const state = service.getCategoryState("pricing_and_plans");

    expect(state.consecutiveUnchangedCount).toBe(0);
    expect(state.isEligible).toBe(false);
  });

  it("should increment counter on approved_unchanged but remain ineligible at 19", () => {
    const service = new EligibilityService(testStorageDir, testFileName);

    for (let i = 0; i < 19; i++) {
      service.recordReviewEvent("pricing_and_plans", "approved_unchanged");
    }

    const state = service.getCategoryState("pricing_and_plans");
    expect(state.consecutiveUnchangedCount).toBe(19);
    expect(state.isEligible).toBe(false);
  });

  it("should trigger isEligible=true when exactly reaching 20 consecutive unchanged reviews for allowed category", () => {
    const service = new EligibilityService(testStorageDir, testFileName);

    for (let i = 0; i < 20; i++) {
      service.recordReviewEvent("pricing_and_plans", "approved_unchanged");
    }

    const state = service.getCategoryState("pricing_and_plans");
    expect(state.consecutiveUnchangedCount).toBe(20);
    expect(state.isEligible).toBe(true);
  });

  it("should NEVER grant isEligible to sensitive non-whitelisted categories even with 25 approvals", () => {
    const service = new EligibilityService(testStorageDir, testFileName);

    for (let i = 0; i < 25; i++) {
      service.recordReviewEvent("billing_and_payment_issues", "approved_unchanged");
    }

    const state = service.getCategoryState("billing_and_payment_issues");
    expect(state.consecutiveUnchangedCount).toBe(25);
    expect(state.isEligible).toBe(false);
  });

  it("should immediately reset counter to 0 and revoke eligibility when reviewer edits a draft", () => {
    const service = new EligibilityService(testStorageDir, testFileName);

    // Reach 20 approvals
    for (let i = 0; i < 20; i++) {
      service.recordReviewEvent("pricing_and_plans", "approved_unchanged");
    }
    expect(service.getCategoryState("pricing_and_plans").isEligible).toBe(true);

    // 21st review has an edit
    const afterEdit = service.recordReviewEvent(
      "pricing_and_plans",
      "approved_edited",
      "Corrected outdated pricing figure"
    );

    expect(afterEdit.consecutiveUnchangedCount).toBe(0);
    expect(afterEdit.isEligible).toBe(false);
    expect(afterEdit.totalEdited).toBe(1);
    expect(afterEdit.lastResetReason).toContain("Reset from 20");
  });

  it("should reset counter to 0 when draft is rejected", () => {
    const service = new EligibilityService(testStorageDir, testFileName);

    for (let i = 0; i < 5; i++) {
      service.recordReviewEvent("standard_feature_questions", "approved_unchanged");
    }

    const afterReject = service.recordReviewEvent(
      "standard_feature_questions",
      "rejected",
      "Hallucinated instructions"
    );

    expect(afterReject.consecutiveUnchangedCount).toBe(0);
    expect(afterReject.isEligible).toBe(false);
    expect(afterReject.totalRejected).toBe(1);
  });

  it("should persist eligibility state across service instantiations", () => {
    const service1 = new EligibilityService(testStorageDir, testFileName);
    for (let i = 0; i < 7; i++) {
      service1.recordReviewEvent("pricing_and_plans", "approved_unchanged");
    }

    // New instance reading from disk
    const service2 = new EligibilityService(testStorageDir, testFileName);
    const state = service2.getCategoryState("pricing_and_plans");

    expect(state.consecutiveUnchangedCount).toBe(7);
  });
});
