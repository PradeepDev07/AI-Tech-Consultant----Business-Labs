import fs from "fs";
import path from "path";
import { EligibilityService } from "../automation/eligibility.service.js";
import { SafetyPolicyService } from "../automation/safety-policy.js";
import { EmailClassifier } from "../classification/classifier.js";
import { DraftService } from "../drafting/draft.service.js";
import { EmailRepository } from "../email/email.repository.js";
import { EmailService } from "../email/email.service.js";
import { FeedbackRepository } from "../feedback/feedback.repository.js";
import { FeedbackService } from "../feedback/feedback.service.js";
import { KnowledgeBrainClient } from "../knowledge-client/knowledge-client.js";
import { KnowledgeLookupResult } from "../knowledge-client/knowledge.types.js";
import { BaseModelProvider, MockModelProvider, OllamaModelProvider } from "../providers/model-provider.js";
import { EVALUATION_DATASET } from "./evaluation-dataset.js";
import { EvaluationCase, EvaluationResult } from "./evaluation.types.js";

async function runEvaluations(): Promise<void> {
  const args = process.argv.slice(2);
  const providerArg =
    args.find((a) => a.startsWith("--provider="))?.split("=")[1] ||
    process.env.MODEL_PROVIDER ||
    "mock";
  const modelArg =
    args.find((a) => a.startsWith("--model="))?.split("=")[1] ||
    process.env.CHAT_MODEL ||
    "nemotron-3-nano:30b-cloud";
  const urlArg =
    args.find((a) => a.startsWith("--url="))?.split("=")[1] ||
    process.env.OLLAMA_BASE_URL ||
    "http://localhost:11434";

  const sharedModelProvider: BaseModelProvider =
    providerArg === "ollama"
      ? new OllamaModelProvider(urlArg, modelArg)
      : new MockModelProvider();

  console.log("==========================================================================");
  console.log(`🧪 TASK 2: INBOX AGENT BENCHMARK EVALUATIONS [${sharedModelProvider.providerName}]`);
  console.log("==========================================================================\n");

  const results: EvaluationResult[] = [];
  const testStorageDir = "storage/test-eval";
  let totalPromptTokens = 0;
  let totalEvalTokens = 0;
  let totalModelDurationMs = 0;

  // Clean test storage
  if (fs.existsSync(testStorageDir)) {
    fs.rmSync(testStorageDir, { recursive: true, force: true });
  }

  for (const testCase of EVALUATION_DATASET) {
    const tStart = Date.now();
    process.stdout.write(`Evaluating [${testCase.id}] ${testCase.name}... `);
    const failures: string[] = [];

    // 1. Isolate Services for this test
    const modelProvider = sharedModelProvider;
    const feedbackRepo = new FeedbackRepository(testStorageDir, `feedback_${testCase.id}.json`);
    const feedbackService = new FeedbackService(feedbackRepo);
    const eligibilityService = new EligibilityService(
      testStorageDir,
      `eligibility_${testCase.id}.json`
    );
    const emailRepository = new EmailRepository(testStorageDir, `emails_${testCase.id}.json`);
    const classifier = new EmailClassifier(modelProvider);
    const draftService = new DraftService(modelProvider, feedbackService);
    const safetyPolicy = new SafetyPolicyService();

    // Seed eligibility if requested in setup
    if (testCase.setup?.categoryEligibility) {
      const { category, consecutiveUnchangedCount } = testCase.setup.categoryEligibility;
      for (let i = 0; i < consecutiveUnchangedCount; i++) {
        eligibilityService.recordReviewEvent(category, "approved_unchanged");
      }
    }

    // Mock Knowledge Client
    const mockKnowledgeClient = {
      queryKnowledgeBrain: async (
        _question: string,
        _options?: any
      ): Promise<KnowledgeLookupResult> => {
        if (testCase.setup?.mockKnowledgeResult) {
          const mk = testCase.setup.mockKnowledgeResult;
          return {
            success: mk.success,
            abstained: mk.abstained,
            abstentionReason: mk.abstentionReason || null,
            answer: mk.answer || "",
            citations: (mk.citations as any) || [],
            error: mk.error,
            latencyMs: 12,
          };
        }

        // Default mock knowledge result
        return {
          success: true,
          abstained: false,
          abstentionReason: null,
          answer: "Brilliant Directories provides standard features for directory setup.",
          citations: [
            {
              article_id: "art_general_01",
              article_title: "General Solution Center Article",
              source_url: "https://support.brilliantdirectories.com/general",
              excerpt: "Standard features are configured in the Admin Dashboard.",
            },
          ],
          latencyMs: 15,
        };
      },
    } as unknown as KnowledgeBrainClient;

    const emailService = new EmailService(
      classifier,
      mockKnowledgeClient,
      draftService,
      safetyPolicy,
      eligibilityService,
      emailRepository
    );

    // 2. Execute email processing
    const actual = await emailService.processEmail({
      from: testCase.input.from,
      subject: testCase.input.subject,
      body: testCase.input.body,
    });

    // 3. Evaluate assertions
    if (testCase.expected.category && actual.category !== testCase.expected.category) {
      failures.push(
        `Category mismatch: expected '${testCase.expected.category}', got '${actual.category}'`
      );
    }

    if (testCase.expected.riskLevel && actual.riskLevel !== testCase.expected.riskLevel) {
      failures.push(
        `Risk level mismatch: expected '${testCase.expected.riskLevel}', got '${actual.riskLevel}'`
      );
    }

    if (testCase.expected.detectedIntentsInclude) {
      for (const intent of testCase.expected.detectedIntentsInclude) {
        if (!actual.detectedIntents.includes(intent)) {
          failures.push(
            `Expected intent '${intent}' missing from detected intents [${actual.detectedIntents.join(", ")}]`
          );
        }
      }
    }

    if (actual.requiresHumanReview !== testCase.expected.requiresHumanReview) {
      failures.push(
        `requiresHumanReview mismatch: expected ${testCase.expected.requiresHumanReview}, got ${actual.requiresHumanReview}`
      );
    }

    if (actual.autoSendEligible !== testCase.expected.autoSendEligible) {
      failures.push(
        `autoSendEligible mismatch: expected ${testCase.expected.autoSendEligible}, got ${actual.autoSendEligible}`
      );
    }

    if (
      testCase.expected.knowledgeStatus &&
      actual.knowledgeStatus !== testCase.expected.knowledgeStatus
    ) {
      failures.push(
        `knowledgeStatus mismatch: expected '${testCase.expected.knowledgeStatus}', got '${actual.knowledgeStatus}'`
      );
    }

    if (testCase.expected.draftMustContain) {
      for (const snippet of testCase.expected.draftMustContain) {
        if (!actual.draft.toLowerCase().includes(snippet.toLowerCase())) {
          failures.push(`Draft missing required text snippet: "${snippet}"`);
        }
      }
    }

    if (testCase.expected.draftMustNotContain) {
      for (const snippet of testCase.expected.draftMustNotContain) {
        if (actual.draft.toLowerCase().includes(snippet.toLowerCase())) {
          failures.push(`Draft contains prohibited text snippet: "${snippet}"`);
        }
      }
    }

    const passed = failures.length === 0;
    const elapsed = Date.now() - tStart;
    console.log(passed ? `✅ PASS (${elapsed}ms)` : `❌ FAIL (${elapsed}ms)`);
    results.push({
      id: testCase.id,
      name: testCase.name,
      passed,
      actual: {
        category: actual.category,
        riskLevel: actual.riskLevel,
        detectedIntents: actual.detectedIntents,
        requiresHumanReview: actual.requiresHumanReview,
        autoSendEligible: actual.autoSendEligible,
        knowledgeStatus: actual.knowledgeStatus,
        consecutiveCount: actual.consecutiveUnchangedApprovals,
      },
      failures,
    });

    if (sharedModelProvider instanceof OllamaModelProvider && (sharedModelProvider as any).lastTelemetry) {
      const telem = (sharedModelProvider as any).lastTelemetry;
      totalPromptTokens += telem.prompt_eval_count || 0;
      totalEvalTokens += telem.eval_count || 0;
      totalModelDurationMs += telem.total_duration_ms || 0;
    }
  }

  // Print results table
  console.log(
    "| ID | Test Case | Category | Auto-Send | Human Review | Result |"
  );
  console.log(
    "|---|---|---|---|---|---|"
  );

  let passedCount = 0;
  for (const r of results) {
    const statusIcon = r.passed ? "✅ PASS" : "❌ FAIL";
    if (r.passed) passedCount++;
    console.log(
      `| ${r.id} | ${r.name} | ${r.actual.category} | ${r.actual.autoSendEligible ? "YES" : "NO"} | ${r.actual.requiresHumanReview ? "REQUIRED" : "OPTIONAL"} | ${statusIcon} |`
    );
    if (!r.passed) {
      for (const f of r.failures) {
        console.log(`   ↳ ❌ ${f}`);
      }
    }
  }

  // Clean test storage
  if (fs.existsSync(testStorageDir)) {
    fs.rmSync(testStorageDir, { recursive: true, force: true });
  }

  console.log("\n==========================================================================");
  console.log(
    `EVALUATION SUMMARY: ${passedCount}/${results.length} PASSED (${Math.round((passedCount / results.length) * 100)}%)`
  );
  console.log(`MODEL PROVIDER:     ${sharedModelProvider.providerName}`);
  if (totalPromptTokens > 0) {
    console.log(`TOTAL PROMPT TOKENS:     ${totalPromptTokens}`);
    console.log(`TOTAL COMPLETION TOKENS: ${totalEvalTokens}`);
    console.log(`TOTAL MODEL TIME:        ${totalModelDurationMs} ms`);
  }
  console.log("==========================================================================");

  if (passedCount < results.length) {
    process.exit(1);
  }
}

runEvaluations().catch((err) => {
  console.error("Evaluation run failed with error:", err);
  process.exit(1);
});
