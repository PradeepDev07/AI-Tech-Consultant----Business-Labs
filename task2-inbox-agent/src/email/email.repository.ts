import fs from "fs";
import path from "path";
import { EmailCategory, ProcessedEmailResult, ReviewStatus } from "./email.types.js";

export class EmailRepository {
  private readonly filePath: string;
  private emails: Map<string, ProcessedEmailResult> = new Map();

  constructor(storageDir = "storage", fileName = "emails.json") {
    this.filePath = path.join(process.cwd(), storageDir, fileName);
    this.loadEmails();
  }

  private loadEmails(): void {
    const dir = path.dirname(this.filePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    if (fs.existsSync(this.filePath)) {
      try {
        const raw = fs.readFileSync(this.filePath, "utf-8");
        const list: ProcessedEmailResult[] = JSON.parse(raw);
        for (const item of list) {
          this.emails.set(item.emailId, item);
        }
      } catch (err) {
        console.error("Failed to load existing emails, starting empty:", err);
      }
    }
  }

  private persist(): void {
    const dir = path.dirname(this.filePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    const list = Array.from(this.emails.values());
    fs.writeFileSync(this.filePath, JSON.stringify(list, null, 2), "utf-8");
  }

  saveEmail(email: ProcessedEmailResult): void {
    this.emails.set(email.emailId, email);
    this.persist();
  }

  getEmailById(emailId: string): ProcessedEmailResult | undefined {
    return this.emails.get(emailId);
  }

  updateEmail(
    emailId: string,
    partial: Partial<ProcessedEmailResult>
  ): ProcessedEmailResult | undefined {
    const existing = this.emails.get(emailId);
    if (!existing) {
      return undefined;
    }

    const updated: ProcessedEmailResult = {
      ...existing,
      ...partial,
      updatedAt: new Date().toISOString(),
    };

    this.emails.set(emailId, updated);
    this.persist();
    return updated;
  }

  listEmails(filter?: {
    category?: EmailCategory;
    status?: ReviewStatus;
    limit?: number;
  }): ProcessedEmailResult[] {
    let result = Array.from(this.emails.values());

    if (filter?.category) {
      result = result.filter((e) => e.category === filter.category);
    }

    if (filter?.status) {
      result = result.filter((e) => e.reviewStatus === filter.status);
    }

    // Sort descending by creation date
    result.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());

    if (filter?.limit && filter.limit > 0) {
      result = result.slice(0, filter.limit);
    }

    return result;
  }

  clear(): void {
    this.emails.clear();
    if (fs.existsSync(this.filePath)) {
      fs.unlinkSync(this.filePath);
    }
  }
}
