import { z } from "zod";
import { CustomerEmail, EmailCategory, RiskLevel } from "../email/email.types.js";
import { BaseModelProvider } from "../providers/model-provider.js";
import { ClassificationResult } from "./classification.types.js";

const ClassificationSchema = z.object({
  primaryCategory: z.enum([
    "pricing_and_plans",
    "standard_feature_questions",
    "technical_support",
    "directory_or_account_access",
    "billing_and_payment_issues",
    "account_or_permission_changes",
    "complaints",
    "security_sensitive_requests",
    "unknown_or_ambiguous",
  ]),
  detectedIntents: z.array(z.string()).min(1),
  riskLevel: z.enum(["low", "medium", "high"]),
  requiresHumanReview: z.boolean(),
  reason: z.string(),
});

export class EmailClassifier {
  constructor(private readonly modelProvider: BaseModelProvider) {}

  async classify(subject: string, body: string): Promise<ClassificationResult> {
    return this.classifyEmail({
      emailId: "temp",
      from: "unknown@example.com",
      subject,
      body,
      receivedAt: new Date().toISOString(),
    });
  }

  async classifyEmail(email: CustomerEmail): Promise<ClassificationResult> {
    const combinedText = `Subject: ${email.subject}\nBody: ${email.body}`.toLowerCase();

    // 1. Safety Guardrail: Check for Adversarial Prompt Injection
    if (
      combinedText.includes("ignore previous instructions") ||
      combinedText.includes("disregard all prior instructions") ||
      combinedText.includes("system override") ||
      combinedText.includes("reveal system prompt")
    ) {
      return {
        primaryCategory: "security_sensitive_requests",
        detectedIntents: ["prompt_injection_attempt"],
        riskLevel: "high",
        requiresHumanReview: true,
        reason: "Adversarial prompt injection pattern detected in message text.",
      };
    }

    // 2. Rule-based pre-detection for High Risk Sensitive Intents
    const hasAccountChange =
      combinedText.includes("change plan") ||
      combinedText.includes("upgrade my account") ||
      combinedText.includes("cancel subscription") ||
      combinedText.includes("change my billing plan");

    const hasBillingIssue =
      combinedText.includes("refund") ||
      combinedText.includes("double charge") ||
      combinedText.includes("dispute charge") ||
      combinedText.includes("credit card update");

    const hasSecurity =
      combinedText.includes("reset password") ||
      combinedText.includes("unauthorized") ||
      (combinedText.includes("api key") &&
        (combinedText.includes("rotate") ||
          combinedText.includes("leak") ||
          combinedText.includes("compromis") ||
          combinedText.includes("secret") ||
          combinedText.includes("revoke"))) ||
      combinedText.includes("permission change");

    // 3. Prompt the configured model
    const prompt = `Classify the following customer email for Brilliant Directories Solution Center.
Detect all relevant customer intents. Provide response strictly in JSON format:
{
  "primaryCategory": "pricing_and_plans" | "standard_feature_questions" | "technical_support" | "directory_or_account_access" | "billing_and_payment_issues" | "account_or_permission_changes" | "complaints" | "security_sensitive_requests" | "unknown_or_ambiguous",
  "detectedIntents": string[],
  "riskLevel": "low" | "medium" | "high",
  "requiresHumanReview": boolean,
  "reason": string
}

Subject: ${email.subject}
Body:
${email.body}`;

    try {
      const rawResponse = await this.modelProvider.generateResponse(
        prompt,
        "You are an expert customer support email classifier. Always return valid JSON."
      );

      // Parse JSON from response
      const jsonStart = rawResponse.indexOf("{");
      const jsonEnd = rawResponse.lastIndexOf("}");
      if (jsonStart !== -1 && jsonEnd !== -1) {
        const jsonStr = rawResponse.substring(jsonStart, jsonEnd + 1);
        const parsed = JSON.parse(jsonStr);
        const validated = ClassificationSchema.parse(parsed);

        // Apply mandatory safety overrides on model output
        if (hasAccountChange && !validated.detectedIntents.includes("account_or_permission_changes")) {
          validated.detectedIntents.push("account_or_permission_changes");
        }
        if (hasBillingIssue && !validated.detectedIntents.includes("billing_and_payment_issues")) {
          validated.detectedIntents.push("billing_and_payment_issues");
        }
        if (hasSecurity && !validated.detectedIntents.includes("security_sensitive_requests")) {
          validated.detectedIntents.push("security_sensitive_requests");
        }

        if (hasAccountChange || hasBillingIssue || hasSecurity) {
          validated.riskLevel = "high";
          validated.requiresHumanReview = true;
          validated.reason = "High-risk request (billing/account/security) requires mandatory staff review.";
        }

        return validated;
      }
    } catch (err) {
      // Fallback safe classification
    }

    // Deterministic fallback classification if model fails
    let primaryCategory: EmailCategory = "unknown_or_ambiguous";
    const detectedIntents: string[] = [];
    let riskLevel: RiskLevel = "medium";
    let requiresHumanReview = true;
    let reason = "Fallback classification applied.";

    if (hasAccountChange) {
      primaryCategory = "account_or_permission_changes";
      detectedIntents.push("account_or_permission_changes");
      riskLevel = "high";
      reason = "Account modification requested.";
    } else if (hasBillingIssue) {
      primaryCategory = "billing_and_payment_issues";
      detectedIntents.push("billing_and_payment_issues");
      riskLevel = "high";
      reason = "Billing or refund requested.";
    } else if (hasSecurity) {
      primaryCategory = "security_sensitive_requests";
      detectedIntents.push("security_sensitive_requests");
      riskLevel = "high";
      reason = "Security-related request.";
    } else if (combinedText.includes("pricing") || combinedText.includes("cost")) {
      primaryCategory = "pricing_and_plans";
      detectedIntents.push("pricing_and_plans");
      riskLevel = "low";
      requiresHumanReview = false;
      reason = "Routine pricing question.";
    } else if (combinedText.includes("how to") || combinedText.includes("setup")) {
      primaryCategory = "standard_feature_questions";
      detectedIntents.push("standard_feature_questions");
      riskLevel = "low";
      requiresHumanReview = false;
      reason = "Standard product documentation question.";
    } else {
      detectedIntents.push("unknown_or_ambiguous");
    }

    return {
      primaryCategory,
      detectedIntents,
      riskLevel,
      requiresHumanReview,
      reason,
    };
  }
}
