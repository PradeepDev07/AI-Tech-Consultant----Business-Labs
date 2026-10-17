import { ClassificationResult } from "../classification/classification.types.js";
import { EmailCategory } from "../email/email.types.js";
import { KnowledgeLookupResult } from "../knowledge-client/knowledge.types.js";
import { ALLOWED_AUTO_SEND_CATEGORIES, CategoryEligibilityState } from "./eligibility.service.js";

export interface AutomationSafetyEvaluation {
  autoSendEligible: boolean;
  requiresHumanReview: boolean;
  reasons: string[];
}

export class SafetyPolicyService {
  evaluateSafety(params: {
    category: EmailCategory;
    classification: ClassificationResult;
    knowledgeResult: KnowledgeLookupResult;
    eligibility: CategoryEligibilityState;
  }): AutomationSafetyEvaluation {
    const { category, classification, knowledgeResult, eligibility } = params;
    const reasons: string[] = [];
    let requiresHumanReview = false;

    // 1. Mandatory Override: Non-allowed auto-send categories can NEVER auto-send
    if (!ALLOWED_AUTO_SEND_CATEGORIES.has(category)) {
      requiresHumanReview = true;
      reasons.push(`Category '${category}' is not an approved low-risk auto-send category.`);
    }

    // 2. Mandatory Override: Consecutive unchanged approvals threshold check (< 20)
    if (eligibility.consecutiveUnchangedCount < 20) {
      requiresHumanReview = true;
      reasons.push(
        `Category '${category}' has ${eligibility.consecutiveUnchangedCount}/20 consecutive unchanged approvals.`
      );
    }

    // 3. Mandatory Override: High Risk level
    if (classification.riskLevel === "high" || classification.riskLevel === "medium") {
      requiresHumanReview = true;
      reasons.push(`Message evaluated at ${classification.riskLevel} risk level (${classification.reason}).`);
    }

    // 4. Mandatory Override: Mixed-intents containing high-risk tasks
    const highRiskIntents = [
      "account_or_permission_changes",
      "billing_and_payment_issues",
      "security_sensitive_requests",
      "prompt_injection_attempt",
      "complaints",
      "directory_or_account_access",
    ];

    const hasHighRiskIntent = classification.detectedIntents.some((intent) =>
      highRiskIntents.includes(intent)
    );
    if (hasHighRiskIntent) {
      requiresHumanReview = true;
      reasons.push("Message contains a sensitive intent (account modification, billing, or security).");
    }

    // 5. Mandatory Override: Knowledge Lookup Failure or Abstention
    if (!knowledgeResult.success) {
      requiresHumanReview = true;
      reasons.push(`Task 1 Knowledge Brain lookup failed: ${knowledgeResult.error || "Service unavailable"}`);
    } else if (knowledgeResult.abstained) {
      requiresHumanReview = true;
      reasons.push(
        `Task 1 Knowledge Brain abstained due to insufficient evidence (${knowledgeResult.abstentionReason || "Unknown reason"})`
      );
    } else if (!knowledgeResult.citations || knowledgeResult.citations.length === 0) {
      requiresHumanReview = true;
      reasons.push("Task 1 response contains no authoritative citations.");
    }

    const autoSendEligible = !requiresHumanReview;
    if (autoSendEligible) {
      reasons.push("All safety criteria met: Low-risk category with 20+ verified unchanged reviews and grounded knowledge.");
    }

    return {
      autoSendEligible,
      requiresHumanReview,
      reasons,
    };
  }
}
