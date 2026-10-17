import { Request, Response, Router } from "express";
import { ApprovalService } from "../approval/approval.service.js";
import { EligibilityService } from "../automation/eligibility.service.js";
import { FeedbackService } from "../feedback/feedback.service.js";

export function createReviewRouter(
  approvalService: ApprovalService,
  eligibilityService: EligibilityService,
  feedbackService: FeedbackService
): Router {
  const router = Router();

  // POST /api/v1/reviews/:emailId/approve - Approve draft unchanged
  router.post("/:emailId/approve", (req: Request, res: Response) => {
    try {
      const emailId = String(req.params.emailId);
      const { reviewedBy = "human_reviewer", reviewerNotes } = req.body;

      const result = approvalService.approveUnchanged(emailId, reviewedBy, reviewerNotes);
      res.json({
        success: true,
        message: "Draft approved unchanged. Consecutive counter incremented.",
        data: result,
      });
    } catch (err: any) {
      const status = err.message.includes("not found") ? 404 : 400;
      res.status(status).json({
        success: false,
        error: err.message,
      });
    }
  });

  // POST /api/v1/reviews/:emailId/edit - Edit draft and approve
  router.post("/:emailId/edit", (req: Request, res: Response) => {
    try {
      const emailId = String(req.params.emailId);
      const { editedDraft, reviewedBy = "human_reviewer", reviewerNotes } = req.body;

      if (!editedDraft) {
        res.status(400).json({
          success: false,
          error: "Field 'editedDraft' is required for editing.",
        });
        return;
      }

      const result = approvalService.approveEdited(
        emailId,
        editedDraft,
        reviewedBy,
        reviewerNotes
      );
      res.json({
        success: true,
        message: "Draft edited and approved. Consecutive counter reset to 0.",
        data: result,
      });
    } catch (err: any) {
      const status = err.message.includes("not found") ? 404 : 400;
      res.status(status).json({
        success: false,
        error: err.message,
      });
    }
  });

  // POST /api/v1/reviews/:emailId/reject - Reject draft
  router.post("/:emailId/reject", (req: Request, res: Response) => {
    try {
      const emailId = String(req.params.emailId);
      const reason =
        req.body.reason ||
        req.body.reviewerNotes ||
        "Draft rejected by reviewer";
      const reviewedBy = req.body.reviewedBy || "human_reviewer";

      const result = approvalService.rejectDraft(emailId, reviewedBy, reason);
      res.json({
        success: true,
        message: "Draft rejected. Consecutive counter reset to 0.",
        data: result,
      });
    } catch (err: any) {
      const status = err.message.includes("not found") ? 404 : 400;
      res.status(status).json({
        success: false,
        error: err.message,
      });
    }
  });

  // POST /api/v1/reviews/:emailId/investigate - Mark investigation needed
  router.post("/:emailId/investigate", (req: Request, res: Response) => {
    try {
      const emailId = String(req.params.emailId);
      const notes =
        req.body.notes ||
        req.body.reviewerNotes ||
        "Further investigation required";
      const reviewedBy = req.body.reviewedBy || "human_reviewer";

      const result = approvalService.markInvestigationNeeded(emailId, reviewedBy, notes);
      res.json({
        success: true,
        message: "Marked for investigation. Consecutive counter reset to 0.",
        data: result,
      });
    } catch (err: any) {
      const status = err.message.includes("not found") ? 404 : 400;
      res.status(status).json({
        success: false,
        error: err.message,
      });
    }
  });

  return router;
}

export function createAutomationRouter(
  eligibilityService: EligibilityService,
  feedbackService: FeedbackService
): Router {
  const router = Router();

  // GET /api/v1/automation/eligibility - View all category counters and auto-send eligibility
  router.get("/eligibility", (_req: Request, res: Response) => {
    res.json({
      success: true,
      data: eligibilityService.getAllCategoryStates(),
    });
  });

  // GET /api/v1/automation/feedback - View review feedback history
  router.get("/feedback", (req: Request, res: Response) => {
    const category = req.query.category as any;
    const history = feedbackService.listAllReviews(category);
    res.json({
      success: true,
      count: history.length,
      data: history,
    });
  });

  return router;
}
