import fs from "fs";
import path from "path";
import { EmailCategory } from "../email/email.types.js";

export const AUTO_SEND_THRESHOLD = 20;

// Low-risk categories eligible for automatic sending once the 20-unchanged threshold is met
export const ALLOWED_AUTO_SEND_CATEGORIES: ReadonlySet<EmailCategory> = new Set([
  "pricing_and_plans",
  "standard_feature_questions",
]);

export interface CategoryEligibilityState {
  consecutiveUnchangedCount: number;
  isEligible: boolean;
  totalApprovedUnchanged: number;
  totalEdited: number;
  totalRejected: number;
  lastResetReason?: string;
  lastUpdated: string;
}

export type EligibilityStore = Record<EmailCategory, CategoryEligibilityState>;

export class EligibilityService {
  private readonly filePath: string;
  private state: EligibilityStore;

  constructor(storageDir = "storage", fileName = "eligibility.json") {
    this.filePath = path.join(process.cwd(), storageDir, fileName);
    this.state = this.getInitialState();
    this.loadState();
  }

  private getInitialState(): EligibilityStore {
    const categories: EmailCategory[] = [
      "pricing_and_plans",
      "standard_feature_questions",
      "technical_support",
      "directory_or_account_access",
      "billing_and_payment_issues",
      "account_or_permission_changes",
      "complaints",
      "security_sensitive_requests",
      "unknown_or_ambiguous",
    ];

    const initial: Partial<EligibilityStore> = {};
    for (const cat of categories) {
      initial[cat] = {
        consecutiveUnchangedCount: 0,
        isEligible: false,
        totalApprovedUnchanged: 0,
        totalEdited: 0,
        totalRejected: 0,
        lastUpdated: new Date().toISOString(),
      };
    }
    return initial as EligibilityStore;
  }

  private loadState(): void {
    const dir = path.dirname(this.filePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    if (fs.existsSync(this.filePath)) {
      try {
        const raw = fs.readFileSync(this.filePath, "utf-8");
        const loaded = JSON.parse(raw);
        this.state = { ...this.getInitialState(), ...loaded };
      } catch (err) {
        this.state = this.getInitialState();
      }
    }
  }

  private saveState(): void {
    const dir = path.dirname(this.filePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(this.filePath, JSON.stringify(this.state, null, 2), "utf-8");
  }

  getCategoryState(category: EmailCategory): CategoryEligibilityState {
    if (!this.state[category]) {
      this.state[category] = {
        consecutiveUnchangedCount: 0,
        isEligible: false,
        totalApprovedUnchanged: 0,
        totalEdited: 0,
        totalRejected: 0,
        lastUpdated: new Date().toISOString(),
      };
    }
    return this.state[category];
  }

  getAllCategoryStates(): EligibilityStore {
    return { ...this.state };
  }

  recordReviewEvent(
    category: EmailCategory,
    action: "approved_unchanged" | "approved_edited" | "rejected" | "investigation_needed",
    reason?: string
  ): CategoryEligibilityState {
    const entry = this.getCategoryState(category);
    const now = new Date().toISOString();

    if (action === "approved_unchanged") {
      entry.consecutiveUnchangedCount += 1;
      entry.totalApprovedUnchanged += 1;

      // Category is eligible ONLY if it reaches threshold AND is in allowed low-risk categories
      if (
        entry.consecutiveUnchangedCount >= AUTO_SEND_THRESHOLD &&
        ALLOWED_AUTO_SEND_CATEGORIES.has(category)
      ) {
        entry.isEligible = true;
      }
    } else {
      // Any edit, rejection, or non-qualifying review RESETS consecutive counter to 0!
      const previousCount = entry.consecutiveUnchangedCount;
      entry.consecutiveUnchangedCount = 0;
      entry.isEligible = false;
      entry.lastResetReason = `Reset from ${previousCount} on action: ${action}${reason ? ` (${reason})` : ""}`;

      if (action === "approved_edited") {
        entry.totalEdited += 1;
      } else if (action === "rejected") {
        entry.totalRejected += 1;
      }
    }

    entry.lastUpdated = now;
    this.saveState();
    return entry;
  }

  clear(): void {
    this.state = this.getInitialState();
    if (fs.existsSync(this.filePath)) {
      fs.unlinkSync(this.filePath);
    }
  }
}
