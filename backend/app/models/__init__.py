"""Backend ORM models and their registration in the shared metadata."""

from app.models.assessment_attempt import AssessmentAttempt, AttemptStatus, HRDecision
from app.models.assessment_retention_processing import AssessmentRetentionProcessing, RetentionProcessingStatus
from app.models.attempt_question_order import AttemptQuestionOrder
from app.models.attempt_event import AttemptEvent, AttemptEventType
from app.models.candidate_answer import CandidateAnswer
from app.models.candidate import Candidate
from app.models.candidate_consent import CandidateConsent
from app.models.exam import Exam, ExamStatus
from app.models.exam_question import ExamQuestion
from app.models.exam_question_option import ExamQuestionOption
from app.models.exam_invitation import ExamInvitation, InvitationStatus
from app.models.exam_invitation_question import ExamInvitationQuestion
from app.models.exam_template import ExamTemplate
from app.models.exam_template_question import ExamTemplateQuestion
from app.models.exam_template_question_option import ExamTemplateQuestionOption
from app.domain.hr_roles import HRRole
from app.models.hr_user import HRUser
from app.models.hr_user_role import HRUserRole
from app.models.recording_metadata import RecordingMetadata

__all__ = [
    "Candidate",
    "CandidateAnswer",
    "CandidateConsent",
    "AssessmentAttempt",
    "AttemptEvent",
    "AttemptEventType",
    "AttemptQuestionOrder",
    "AttemptStatus",
    "AssessmentRetentionProcessing",
    "RetentionProcessingStatus",
    "HRDecision",
    "Exam",
    "ExamInvitation",
    "ExamInvitationQuestion",
    "ExamStatus",
    "ExamQuestion",
    "ExamQuestionOption",
    "HRUser",
    "HRRole",
    "HRUserRole",
    "ExamTemplate",
    "ExamTemplateQuestion",
    "ExamTemplateQuestionOption",
    "InvitationStatus",
    "RecordingMetadata",
]
