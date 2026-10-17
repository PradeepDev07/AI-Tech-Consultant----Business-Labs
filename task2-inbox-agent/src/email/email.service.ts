import crypto from "crypto";
import { EligibilityService } from "../automation/eligibility.service.js";
import { SafetyPolicyService } from "../automation/safety-policy.js";
import { EmailClassifier } from "../classification/classifier.js";
import { DraftService } from "../drafting/draft.service.js";
import { KnowledgeBrainClient } from "../knowledge-client/knowledge-client.js";
import { EmailRepository } from "./email.repository.js";
import {
  CustomerEmail,
  EmailCategory,
  InboundEmailPayload,
  ProcessedEmailResult,
  ReviewStatus,
} from "./email.types.js";
import { validateInboundEmail } from "./email.validation.js";

export class EmailService {
  constructor(
    private readonly classifier: EmailClassifier,
    private readonly knowledgeClient: KnowledgeBrainClient,
    private readonly draftService: DraftService,
    private readonly safetyPolicy: SafetyPolicyService,
    private readonly eligibilityService: EligibilityService,
    private readonly emailRepository: EmailRepository
  ) {}

  async processEmail(rawPayload: InboundEmailPayload): Promise<ProcessedEmailResult> {
    const validated = validateInboundEmail(rawPayload);

    const emailId = validated.emailId || `email_${crypto.randomUUID()}`;
    const receivedAt = validated.receivedAt || new Date().toISOString();

    const customerEmail: CustomerEmail = {
      emailId,
      from: validated.from,
      to: validated.to,
      subject: validated.subject,
      body: validated.body,
      receivedAt,
    };

    // 1. Classification & Prompt Injection Defense
    const classification = await this.classifier.classify(
      customerEmail.subject,
      customerEmail.body
    );

    // 2. Fetch current category automation eligibility
    const eligibility = this.eligibilityService.getCategoryState(classification.primaryCategory);

    // 3. Knowledge Lookup from Task 1 Knowledge Brain API (Polite, bounded, timeout-guarded)
    // For non-informational categories like complaints or billing changes, we still query if relevant or let it fail gracefully
    const knowledgeResult = await this.knowledgeClient.queryKnowledgeBrain(
      customerEmail.body,
      { top_k: 3 }
    );

    // 4. Grounded Drafting with few-shot memory
    const draftResult = await this.draftService.generateDraft({
      email: customerEmail,
      category: classification.primaryCategory,
      knowledgeResult,
    });

    // 5. Evaluate Safety Policy and 20-unchanged-approvals rule
    const safetyEvaluation = this.safetyPolicy.evaluateSafety({
      category: classification.primaryCategory,
      classification,
      knowledgeResult,
      eligibility,
    });

    // Additional check: If draft has unverified claims, enforce human review
    if (!draftResult.isGrounded && draftResult.unsupportedClaims.length > 0) {
      safetyEvaluation.autoSendEligible = false;
      safetyEvaluation.requiresHumanReview = true;
      safetyEvaluation.reasons.push(
        `Draft contains potential unverified claims: ${draftResult.unsupportedClaims.join("; ")}`
      );
    }

    // Determine initial review status
    const reviewStatus: ReviewStatus = safetyEvaluation.autoSendEligible
      ? "auto_sent"
      : "pending";

    // Format citations as evidence
    const evidence = (knowledgeResult.citations || []).map((c) => ({
      articleId: c.article_id,
      articleTitle: c.article_title,
      sourceUrl: c.source_url,
      heading: c.heading || null,
      excerpt: c.excerpt,
      relevanceScore: c.relevance_score || null,
    }));

    const knowledgeStatus = !knowledgeResult.success
      ? ("failed" as const)
      : knowledgeResult.abstained
      ? ("insufficient_evidence" as const)
      : ("success" as const);

    const now = new Date().toISOString();
    const processedResult: ProcessedEmailResult = {
      emailId,
      from: customerEmail.from,
      subject: customerEmail.subject,
      body: customerEmail.body,
      category: classification.primaryCategory,
      detectedIntents: classification.detectedIntents,
      riskLevel: classification.riskLevel,
      requiresHumanReview: safetyEvaluation.requiresHumanReview,
      reviewStatus,
      draft: draftResult.draftText,
      evidence,
      knowledgeStatus,
      autoSendEligible: safetyEvaluation.autoSendEligible,
      consecutiveUnchangedApprovals: eligibility.consecutiveUnchangedCount,
      reasons: safetyEvaluation.reasons,
      reviewedBy: reviewStatus === "auto_sent" ? "system_automation" : null,
      reviewedAt: reviewStatus === "auto_sent" ? now : null,
      reviewerNotes: reviewStatus === "auto_sent" ? "Auto-sent under 20-approval rule" : null,
      createdAt: now,
      updatedAt: now,
    };

    // Save to file-backed persistent repository
    this.emailRepository.saveEmail(processedResult);

    return processedResult;
  }

  getEmailById(emailId: string): ProcessedEmailResult | undefined {
    return this.emailRepository.getEmailById(emailId);
  }

  listEmails(filter?: {
    category?: EmailCategory;
    status?: ReviewStatus;
    limit?: number;
  }): ProcessedEmailResult[] {
    return this.emailRepository.listEmails(filter);
  }
}
