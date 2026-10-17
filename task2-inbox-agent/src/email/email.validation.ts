import { z } from "zod";

export const InboundEmailSchema = z.preprocess(
  (input: any) => {
    if (input && typeof input === "object") {
      let rawFrom = input.from || input.sender;
      if (!rawFrom || typeof rawFrom !== "string" || !rawFrom.includes("@")) {
        rawFrom = "customer@example.com";
      }
      return {
        ...input,
        from: rawFrom.trim(),
      };
    }
    return input;
  },
  z.object({
    emailId: z.string().optional(),
    from: z.string().email("Invalid sender email address"),
    to: z.string().email().optional(),
    subject: z.string().min(1, "Subject cannot be empty").max(300, "Subject too long"),
    body: z.string().min(2, "Body must contain at least 2 characters").max(10000, "Body too long"),
    receivedAt: z.string().datetime({ offset: true }).optional(),
  })
);

export type ValidatedInboundEmail = z.infer<typeof InboundEmailSchema>;

export function validateInboundEmail(payload: unknown): ValidatedInboundEmail {
  return InboundEmailSchema.parse(payload);
}
