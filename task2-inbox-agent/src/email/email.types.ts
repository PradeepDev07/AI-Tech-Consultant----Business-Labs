export type EmailCategory =
  | "pricing_and_plans"
  | "standard_feature_questions"
  | "technical_support"
  | "directory_or_account_access"
  | "billing_and_payment_issues"
  | "account_or_permission_changes"
  | "complaints"
  | "security_sensitive_requests"
  | "unknown_or_ambiguous";

export type RiskLevel = "low" | "medium" | "high";

export type ReviewStatus =
  | "pending"
  | "approved_unchanged"
  | "approved_edited"
  | "rejected"
  | "investigation_needed"
  | "auto_sent";

export interface CustomerEmail {
  emailId: string;
  from: string;
  to?: string;
  subject: string;
  body: string;
  receivedAt: string;
}

export interface InboundEmailPayload {
  emailId?: string;
  from: string;
  to?: string;
  subject: string;
  body: string;
  receivedAt?: string;
}

export interface ProcessedEmailResult {
  emailId: string;
  from: string;
  subject: string;
  body: string;
  category: EmailCategory;
  detectedIntents: string[];
  riskLevel: RiskLevel;
  requiresHumanReview: boolean;
  reviewStatus: ReviewStatus;
  draft: string;
  evidence: Array<{
    articleId: string;
    articleTitle: string;
    sourceUrl: string;
    heading?: string | null;
    excerpt: string;
    relevanceScore?: number | null;
  }>;
  knowledgeStatus: "success" | "insufficient_evidence" | "failed" | "skipped";
  autoSendEligible: boolean;
  consecutiveUnchangedApprovals: number;
  reasons: string[];
  reviewedBy?: string | null;
  reviewedAt?: string | null;
  reviewerNotes?: string | null;
  createdAt: string;
  updatedAt: string;
}
