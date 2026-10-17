import { EmailCategory } from "../email/email.types.js";
import { FeedbackRepository } from "./feedback.repository.js";
import { FeedbackRecord } from "./feedback.types.js";

export class FeedbackService {
  constructor(private readonly repository: FeedbackRepository) {}

  recordReview(record: FeedbackRecord): void {
    this.repository.saveReview(record);
  }

  getRelevantFeedbackForDrafting(category: EmailCategory, limit = 2): FeedbackRecord[] {
    // Prefer approved unchanged examples first, then edited examples with corrections
    const approved = this.repository.listReviews({
      category,
      isUnchanged: true,
      limit,
    });

    if (approved.length >= limit) {
      return approved;
    }

    // Include edited examples to show corrections
    const edited = this.repository.listReviews({
      category,
      isUnchanged: false,
      limit: limit - approved.length,
    });

    return [...approved, ...edited];
  }

  getReview(emailId: string): FeedbackRecord | undefined {
    return this.repository.getReviewByEmailId(emailId);
  }

  listAllReviews(category?: EmailCategory): FeedbackRecord[] {
    return this.repository.listReviews({ category });
  }
}
