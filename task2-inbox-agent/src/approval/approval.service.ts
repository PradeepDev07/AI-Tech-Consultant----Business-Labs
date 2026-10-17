import { CategoryEligibilityState, EligibilityService } from "../automation/eligibility.service.js";
import { EmailRepository } from "../email/email.repository.js";
import { ProcessedEmailResult } from "../email/email.types.js";
import { FeedbackService } from "../feedback/feedback.service.js";

export interface ReviewActionResult {
  email: ProcessedEmailResult;
  eligibility: CategoryEligibilityState;
}

export class ApprovalService {
  constructor(
    private readonly emailRepository: EmailRepository,
    private readonly eligibilityService: EligibilityService,
    private readonly feedbackService: FeedbackService
  ) {}

  approveUnchanged(
    emailId: string,
    reviewedBy: string,
    reviewerNotes?: string
  ): ReviewActionResult {
    const email = this.emailRepository.getEmailById(emailId);
    if (!email) {
      throw new Error(`Email not found: ${emailId}`);
    }

    const now = new Date().toISOString();
    const eligibility = this.eligibilityService.recordReviewEvent(
      email.category,
      "approved_unchanged"
    );

    // Save feedback record for few-shot retrieval
    this.feedbackService.recordReview({
      id: `rev_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
      emailId: email.emailId,
      category: email.category,
      detectedIntents: email.detectedIntents,
      originalDraft: email.draft,
      finalDraft: email.draft,
      action: "approved_unchanged",
      isUnchanged: true,
      reason: reviewerNotes || "Approved without edits",
      reviewedBy,
      reviewedAt: now,
    });

    const updated = this.emailRepository.updateEmail(emailId, {
      reviewStatus: "approved_unchanged",
      requiresHumanReview: false,
      reviewedBy,
      reviewedAt: now,
      reviewerNotes: reviewerNotes || "Approved without edits",
      consecutiveUnchangedApprovals: eligibility.consecutiveUnchangedCount,
      autoSendEligible: eligibility.isEligible,
    })!;

    return {
      email: updated,
      eligibility,
    };
  }

  approveEdited(
    emailId: string,
    editedDraft: string,
    reviewedBy: string,
    reviewerNotes?: string
  ): ReviewActionResult {
    const email = this.emailRepository.getEmailById(emailId);
    if (!email) {
      throw new Error(`Email not found: ${emailId}`);
    }

    if (!editedDraft || editedDraft.trim().length === 0) {
      throw new Error("Edited draft cannot be empty.");
    }

    const now = new Date().toISOString();
    // Edits reset the consecutive unchanged counter for this category!
    const eligibility = this.eligibilityService.recordReviewEvent(
      email.category,
      "approved_edited",
      reviewerNotes || "Draft modified by reviewer"
    );

    this.feedbackService.recordReview({
      id: `rev_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
      emailId: email.emailId,
      category: email.category,
      detectedIntents: email.detectedIntents,
      originalDraft: email.draft,
      finalDraft: editedDraft,
      action: "approved_edited",
      isUnchanged: false,
      reason: reviewerNotes || "Human reviewer adjusted wording/details",
      reviewedBy,
      reviewedAt: now,
    });

    const updated = this.emailRepository.updateEmail(emailId, {
      draft: editedDraft,
      reviewStatus: "approved_edited",
      requiresHumanReview: false,
      reviewedBy,
      reviewedAt: now,
      reviewerNotes: reviewerNotes || "Draft modified and approved",
      consecutiveUnchangedApprovals: eligibility.consecutiveUnchangedCount,
      autoSendEligible: eligibility.isEligible,
    })!;

    return {
      email: updated,
      eligibility,
    };
  }

  rejectDraft(emailId: string, reviewedBy: string, reason: string): ReviewActionResult {
    const email = this.emailRepository.getEmailById(emailId);
    if (!email) {
      throw new Error(`Email not found: ${emailId}`);
    }

    const now = new Date().toISOString();
    // Rejections reset the consecutive counter
    const eligibility = this.eligibilityService.recordReviewEvent(
      email.category,
      "rejected",
      reason
    );

    this.feedbackService.recordReview({
      id: `rev_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
      emailId: email.emailId,
      category: email.category,
      detectedIntents: email.detectedIntents,
      originalDraft: email.draft,
      finalDraft: "",
      action: "rejected",
      isUnchanged: false,
      reason,
      reviewedBy,
      reviewedAt: now,
    });

    const updated = this.emailRepository.updateEmail(emailId, {
      reviewStatus: "rejected",
      requiresHumanReview: true,
      reviewedBy,
      reviewedAt: now,
      reviewerNotes: reason,
      consecutiveUnchangedApprovals: eligibility.consecutiveUnchangedCount,
      autoSendEligible: eligibility.isEligible,
    })!;

    return {
      email: updated,
      eligibility,
    };
  }

  markInvestigationNeeded(
    emailId: string,
    reviewedBy: string,
    notes: string
  ): ReviewActionResult {
    const email = this.emailRepository.getEmailById(emailId);
    if (!email) {
      throw new Error(`Email not found: ${emailId}`);
    }

    const now = new Date().toISOString();
    const eligibility = this.eligibilityService.recordReviewEvent(
      email.category,
      "investigation_needed",
      notes
    );

    this.feedbackService.recordReview({
      id: `rev_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
      emailId: email.emailId,
      category: email.category,
      detectedIntents: email.detectedIntents,
      originalDraft: email.draft,
      finalDraft: email.draft,
      action: "investigation_needed",
      isUnchanged: false,
      reason: notes,
      reviewedBy,
      reviewedAt: now,
    });

    const updated = this.emailRepository.updateEmail(emailId, {
      reviewStatus: "investigation_needed",
      requiresHumanReview: true,
      reviewedBy,
      reviewedAt: now,
      reviewerNotes: notes,
      consecutiveUnchangedApprovals: eligibility.consecutiveUnchangedCount,
      autoSendEligible: eligibility.isEligible,
    })!;

    return {
      email: updated,
      eligibility,
    };
  }
}
