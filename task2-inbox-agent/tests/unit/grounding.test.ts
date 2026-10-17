import { describe, expect, it } from "vitest";
import { GroundingVerifier } from "../../src/drafting/grounding.js";

describe("GroundingVerifier", () => {
  const verifier = new GroundingVerifier();

  const citations = [
    {
      article_id: "art_1",
      article_title: "How to Configure Google Maps",
      source_url: "https://support.brilliantdirectories.com/google-maps",
      excerpt: "Paste your API key in Settings > Integrations.",
    },
  ];

  it("should pass grounded draft with preserved citation URL", () => {
    const draft = `Hello, you can configure Google Maps under Settings > Integrations.
For more details, visit: https://support.brilliantdirectories.com/google-maps`;

    const result = verifier.verifyGrounding(draft, citations);
    expect(result.isGrounded).toBe(true);
    expect(result.unsupportedClaims.length).toBe(0);
    expect(result.preservedCitations).toContain("https://support.brilliantdirectories.com/google-maps");
  });

  it("should detect prohibited action claim: 'I have refunded your payment'", () => {
    const draft = `Hello, I have refunded your payment of $100.
Visit https://support.brilliantdirectories.com/google-maps`;

    const result = verifier.verifyGrounding(draft, citations);
    expect(result.isGrounded).toBe(false);
    expect(result.unsupportedClaims.length).toBeGreaterThan(0);
  });

  it("should detect prohibited action claim: 'I have reset your password'", () => {
    const draft = `Dear customer, I have reset your password to Temp123!
Please visit https://support.brilliantdirectories.com/google-maps`;

    const result = verifier.verifyGrounding(draft, citations);
    expect(result.isGrounded).toBe(false);
    expect(result.unsupportedClaims.length).toBeGreaterThan(0);
  });
});
