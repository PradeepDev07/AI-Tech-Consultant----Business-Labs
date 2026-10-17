import { EmailCategory, RiskLevel } from "../email/email.types.js";

export interface ClassificationResult {
  primaryCategory: EmailCategory;
  detectedIntents: string[];
  riskLevel: RiskLevel;
  requiresHumanReview: boolean;
  reason: string;
}
