import fs from "fs";
import path from "path";
import { FeedbackFilter, FeedbackRecord } from "./feedback.types.js";

export class FeedbackRepository {
  private readonly filePath: string;
  private cache: Map<string, FeedbackRecord> = new Map();

  constructor(storageDir = "storage", fileName = "reviews.json") {
    this.filePath = path.join(process.cwd(), storageDir, fileName);
    this.initStorage();
  }

  private initStorage(): void {
    const dir = path.dirname(this.filePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    if (fs.existsSync(this.filePath)) {
      try {
        const raw = fs.readFileSync(this.filePath, "utf-8");
        const list = JSON.parse(raw) as FeedbackRecord[];
        for (const item of list) {
          this.cache.set(item.emailId, item);
        }
      } catch (err) {
        // If file is empty or corrupted, start fresh
        this.cache.clear();
      }
    }
  }

  private persist(): void {
    const dir = path.dirname(this.filePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    const list = Array.from(this.cache.values());
    fs.writeFileSync(this.filePath, JSON.stringify(list, null, 2), "utf-8");
  }

  saveReview(record: FeedbackRecord): void {
    this.cache.set(record.emailId, record);
    this.persist();
  }

  getReviewByEmailId(emailId: string): FeedbackRecord | undefined {
    return this.cache.get(emailId);
  }

  listReviews(filter?: FeedbackFilter): FeedbackRecord[] {
    let results = Array.from(this.cache.values());

    if (filter?.category) {
      results = results.filter((r) => r.category === filter.category);
    }
    if (filter?.isUnchanged !== undefined) {
      results = results.filter((r) => r.isUnchanged === filter.isUnchanged);
    }

    // Sort descending by reviewedAt
    results.sort((a, b) => new Date(b.reviewedAt).getTime() - new Date(a.reviewedAt).getTime());

    if (filter?.limit && filter.limit > 0) {
      results = results.slice(0, filter.limit);
    }

    return results;
  }

  clear(): void {
    this.cache.clear();
    if (fs.existsSync(this.filePath)) {
      fs.unlinkSync(this.filePath);
    }
  }
}
