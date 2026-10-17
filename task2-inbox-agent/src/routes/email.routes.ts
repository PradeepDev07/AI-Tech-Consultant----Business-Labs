import { Request, Response, Router } from "express";
import { EmailService } from "../email/email.service.js";
import { EmailCategory, ReviewStatus } from "../email/email.types.js";

export function createEmailRouter(emailService: EmailService): Router {
  const router = Router();

  // POST /api/v1/emails - Process an inbound email
  router.post("/", async (req: Request, res: Response) => {
    try {
      const result = await emailService.processEmail(req.body);
      res.status(201).json({
        success: true,
        data: result,
      });
    } catch (err: any) {
      res.status(400).json({
        success: false,
        error: err.message || "Failed to process email",
      });
    }
  });

  // GET /api/v1/emails - List processed emails with optional filters
  router.get("/", (req: Request, res: Response) => {
    try {
      const category = req.query.category as EmailCategory | undefined;
      const status = req.query.status as ReviewStatus | undefined;
      const limit = req.query.limit ? parseInt(req.query.limit as string, 10) : undefined;

      const emails = emailService.listEmails({ category, status, limit });
      res.json({
        success: true,
        count: emails.length,
        data: emails,
      });
    } catch (err: any) {
      res.status(500).json({
        success: false,
        error: err.message || "Failed to list emails",
      });
    }
  });

  // GET /api/v1/emails/:emailId - Get a single email and draft
  router.get("/:emailId", (req: Request, res: Response) => {
    try {
      const emailId = String(req.params.emailId);
      const email = emailService.getEmailById(emailId);
      if (!email) {
        res.status(404).json({
          success: false,
          error: `Email not found: ${emailId}`,
        });
        return;
      }

      res.json({
        success: true,
        data: email,
      });
    } catch (err: any) {
      res.status(500).json({
        success: false,
        error: err.message || "Failed to get email",
      });
    }
  });

  return router;
}
