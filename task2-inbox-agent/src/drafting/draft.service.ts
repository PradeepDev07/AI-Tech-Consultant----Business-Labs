import { CustomerEmail } from "../email/email.types.js";
import { FeedbackService } from "../feedback/feedback.service.js";
import { KnowledgeLookupResult } from "../knowledge-client/knowledge.types.js";
import { BaseModelProvider } from "../providers/model-provider.js";
import { buildDraftPrompt, DRAFT_SYSTEM_PROMPT } from "./draft.prompts.js";
import { GroundingVerifier } from "./grounding.js";

export interface DraftGenerationResult {
  draftText: string;
  isGrounded: boolean;
  unsupportedClaims: string[];
  preservedCitations: string[];
}

export class DraftService {
  private readonly groundingVerifier: GroundingVerifier;

  constructor(
    private readonly modelProvider: BaseModelProvider,
    private readonly feedbackService: FeedbackService
  ) {
    this.groundingVerifier = new GroundingVerifier();
  }

  async generateDraft(params: {
    email: CustomerEmail;
    category: any;
    knowledgeResult: KnowledgeLookupResult;
  }): Promise<DraftGenerationResult> {
    const { email, category, knowledgeResult } = params;

    // Retrieve relevant historical feedback for few-shot guidance
    const historicalFeedback = this.feedbackService.getRelevantFeedbackForDrafting(category, 2);

    // If Task 1 abstained, failed, or found no evidence, output a safe hold draft
    if (!knowledgeResult.success || knowledgeResult.abstained || !knowledgeResult.answer) {
      const safeDraft =
        `Dear Customer,\n\n` +
        `Thank you for contacting Brilliant Directories Support regarding "${email.subject}".\n\n` +
        `We have forwarded your specific request to our technical team for review. A support specialist will follow up with you shortly with further information.\n\n` +
        `Best regards,\n` +
        `Brilliant Directories Support Team`;

      return {
        draftText: safeDraft,
        isGrounded: true,
        unsupportedClaims: [],
        preservedCitations: [],
      };
    }

    // Build grounded prompt
    const prompt = buildDraftPrompt({
      email,
      knowledgeResult,
      historicalFeedback,
    });

    const rawDraft = await this.modelProvider.generateResponse(prompt, DRAFT_SYSTEM_PROMPT);

    // Verify grounding
    const groundingCheck = this.groundingVerifier.verifyGrounding(
      rawDraft,
      knowledgeResult.citations
    );

    return {
      draftText: rawDraft,
      isGrounded: groundingCheck.isGrounded,
      unsupportedClaims: groundingCheck.unsupportedClaims,
      preservedCitations: groundingCheck.preservedCitations,
    };
  }
}
