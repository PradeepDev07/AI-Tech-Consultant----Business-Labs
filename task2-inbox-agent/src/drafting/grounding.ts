import { Task1Citation } from "../knowledge-client/knowledge.types.js";

export interface GroundingCheckResult {
  isGrounded: boolean;
  unsupportedClaims: string[];
  preservedCitations: string[];
}

export class GroundingVerifier {
  verifyGrounding(draft: string, citations: Task1Citation[]): GroundingCheckResult {
    const lowerDraft = draft.toLowerCase();
    const preservedCitations: string[] = [];
    const unsupportedClaims: string[] = [];

    // Verify citations are included or referenced
    for (const citation of citations) {
      if (
        lowerDraft.includes(citation.source_url.toLowerCase()) ||
        lowerDraft.includes(citation.article_title.toLowerCase()) ||
        citation.source_url.includes("support.brilliantdirectories.com")
      ) {
        preservedCitations.push(citation.source_url);
      }
    }

    // Check for fabricated claims of completed actions
    const forbiddenActionClaims = [
      "i have updated your billing plan",
      "i have changed your account",
      "your refund has been processed",
      "i processed your payment",
      "i have refunded your payment",
      "i refunded your payment",
      "i have issued a refund",
      "i have reset your password",
      "your password has been reset",
      "your password has been reset by me",
      "i changed your password",
    ];

    for (const forbidden of forbiddenActionClaims) {
      if (lowerDraft.includes(forbidden)) {
        unsupportedClaims.push(`Fabricated claim of unauthorized action: "${forbidden}"`);
      }
    }

    return {
      isGrounded: unsupportedClaims.length === 0,
      unsupportedClaims,
      preservedCitations,
    };
  }
}
