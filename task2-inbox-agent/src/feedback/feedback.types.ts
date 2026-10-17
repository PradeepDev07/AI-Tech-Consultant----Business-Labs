import { EmailCategory, ReviewStatus } from "../email/email.types.js";

export interface FeedbackRecord {
  id: string;
  emailId: string;
  category: EmailCategory;
  detectedIntents: string[];
  originalDraft: string;
  finalDraft: string;
  action: "approved_unchanged" | "approved_edited" | "rejected" | "investigation_needed";
  isUnchanged: boolean;
  reason?: string;
  reviewedBy: string;
  reviewedAt: string;
  modelProvider?: string;
}

export interface FeedbackFilter {
  category?: EmailCategory;
  isUnchanged?: boolean;
  limit?: number;
}
