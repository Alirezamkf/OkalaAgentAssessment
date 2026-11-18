"""Backend ORM models and their registration in the shared metadata."""

from app.models.assessment_attempt import AssessmentAttempt, AttemptStatus, HRDecision
from app.models.assessment_retention_processing import AssessmentRetentionProcessing, RetentionProcessingStatus
from app.models.attempt_question_order import AttemptQuestionOrder
from app.models.attempt_event import AttemptEvent
from app.models.candidate_answer import CandidateAnswer
from app.models.candidate import Candidate
from app.models.candidate_consent import CandidateConsent
from app.models.exam import Exam, ExamStatus
from app.models.exam_question import ExamQuestion
from app.models.exam_question_option import ExamQuestionOption
from app.models.exam_invitation import ExamInvitation, InvitationStatus
from app.models.exam_invitation_question import ExamInvitationQuestion
from app.models.hr_user import HRUser
from app.models.question import Question
from app.models.question_option import QuestionOption
from app.models.question_set import QuestionSet
from app.models.question_set_item import QuestionSetItem
from app.models.recording_metadata import RecordingMetadata

__all__ = [
    "Candidate",
    "CandidateAnswer",
    "CandidateConsent",
    "AssessmentAttempt",
    "AttemptEvent",
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
    "InvitationStatus",
    "Question",
    "QuestionOption",
    "QuestionSet",
    "QuestionSetItem",
    "RecordingMetadata",
]
