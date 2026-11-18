"""Backend ORM models and their registration in the shared metadata."""

from app.models.assessment_attempt import AssessmentAttempt, AttemptStatus
from app.models.attempt_event import AttemptEvent
from app.models.candidate_answer import CandidateAnswer
from app.models.candidate import Candidate
from app.models.candidate_consent import CandidateConsent, ConsentDecision
from app.models.exam import Exam, ExamStatus
from app.models.exam_invitation import ExamInvitation, InvitationStatus
from app.models.exam_invitation_question import ExamInvitationQuestion
from app.models.hr_user import HRUser
from app.models.question import Question
from app.models.question_option import QuestionOption
from app.models.recording_metadata import RecordingMetadata

__all__ = [
    "Candidate",
    "CandidateAnswer",
    "CandidateConsent",
    "ConsentDecision",
    "AssessmentAttempt",
    "AttemptEvent",
    "AttemptStatus",
    "Exam",
    "ExamInvitation",
    "ExamInvitationQuestion",
    "ExamStatus",
    "HRUser",
    "InvitationStatus",
    "Question",
    "QuestionOption",
    "RecordingMetadata",
]
