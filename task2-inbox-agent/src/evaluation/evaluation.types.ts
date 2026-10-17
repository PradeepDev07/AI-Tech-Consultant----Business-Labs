import { EmailCategory, RiskLevel } from "../email/email.types.js";

export interface EvaluationCase {
  id: string;
  name: string;
  description: string;
  setup?: {
    categoryEligibility?: {
      category: EmailCategory;
      consecutiveUnchangedCount: number;
    };
    mockKnowledgeResult?: {
      success: boolean;
      abstained: boolean;
      abstentionReason?: string | null;
      answer?: string;
      citations?: Array<{
        article_id: string;
        article_title: string;
        source_url: string;
        excerpt: string;
        relevance_score?: number;
      }>;
      error?: string;
    };
  };
  input: {
    from: string;
    subject: string;
    body: string;
  };
  expected: {
    category?: EmailCategory;
    riskLevel?: RiskLevel;
    detectedIntentsInclude?: string[];
    requiresHumanReview: boolean;
    autoSendEligible: boolean;
    knowledgeStatus?: "success" | "insufficient_evidence" | "failed" | "skipped";
    draftMustContain?: string[];
    draftMustNotContain?: string[];
  };
}

export interface EvaluationResult {
  id: string;
  name: string;
  passed: boolean;
  actual: {
    category: EmailCategory;
    riskLevel: RiskLevel;
    detectedIntents: string[];
    requiresHumanReview: boolean;
    autoSendEligible: boolean;
    knowledgeStatus: string;
    consecutiveCount: number;
  };
  failures: string[];
}
