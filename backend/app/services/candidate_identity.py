"""Candidate identity matching and reassignment logic."""

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.candidate import Candidate


CandidateMatchStatus = Literal["reuse", "new", "conflict"]


@dataclass(frozen=True)
class CandidateMatch:
    """Result of a conservative candidate identity match."""

    status: CandidateMatchStatus
    candidate: Candidate | None = None
    reason: str | None = None


def normalize_name(value: str) -> str:
    """Normalize names for matching without using name alone as identity proof."""

    return " ".join(value.strip().split()).casefold()


def normalize_email(value: str | None) -> str | None:
    """Normalize an email for lookup and persistence."""

    if value is None:
        return None
    normalized = value.strip().lower()
    return normalized or None


def normalize_phone(value: str | None) -> str | None:
    """Normalize a phone conservatively without assuming a country code."""

    if value is None:
        return None
    digits = "".join(character for character in value if character.isdigit())
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits or None


def names_match(candidate: Candidate, first_name: str, last_name: str) -> bool:
    """Check whether the incoming name agrees with the existing candidate name."""

    return (
        normalize_name(candidate.first_name) == normalize_name(first_name)
        and normalize_name(candidate.last_name) == normalize_name(last_name)
    )


def resolve_candidate(
    db: Session,
    *,
    first_name: str,
    last_name: str,
    email: str | None = None,
    phone: str | None = None,
) -> CandidateMatch:
    """Resolve a candidate conservatively across repeated registrations.

    Email or phone may match a known candidate when the names agree. If email
    and phone point to different candidates, or matching contact data is
    ambiguous, this returns a conflict instead of guessing.
    """

    first_name = " ".join(first_name.strip().split())
    last_name = " ".join(last_name.strip().split())
    if not first_name or not last_name:
        raise ValueError("first_name and last_name are required")

    email = normalize_email(email)
    phone = normalize_phone(phone)
    if email is None and phone is None:
        raise ValueError("at least one of email or phone is required")

    candidates = list(db.scalars(select(Candidate)).all())

    email_matches = [
        candidate
        for candidate in candidates
        if email is not None and normalize_email(candidate.email) == email
    ]
    phone_matches = [
        candidate
        for candidate in candidates
        if phone is not None and normalize_phone(candidate.phone) == phone
    ]

    if len(email_matches) > 1 or len(phone_matches) > 1:
        return CandidateMatch(
            "conflict",
            reason="Multiple candidates match the supplied contact information",
        )

    email_match = email_matches[0] if email_matches else None
    phone_match = phone_matches[0] if phone_matches else None

    if email_match is not None and phone_match is not None:
        if email_match.id != phone_match.id:
            return CandidateMatch(
                "conflict",
                reason="Email and phone belong to different candidates",
            )

    matching_candidate = email_match or phone_match
    if matching_candidate is not None:
        if not names_match(matching_candidate, first_name, last_name):
            return CandidateMatch(
                "conflict",
                reason="Contact information matches a candidate with a different name",
            )
        return CandidateMatch("reuse", candidate=matching_candidate)

    # Names alone are intentionally not sufficient to reuse or merge a candidate.
    return CandidateMatch("new")


def get_or_create_candidate(
    db: Session,
    *,
    first_name: str,
    last_name: str,
    email: str | None = None,
    phone: str | None = None,
) -> Candidate:
    """Reuse a safely matched candidate or create a new one without merging conflicts."""

    match = resolve_candidate(
        db,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
    )
    if match.status == "conflict":
        raise ValueError(match.reason or "Candidate identity conflict")

    normalized_email = normalize_email(email)
    normalized_phone = normalize_phone(phone)

    if match.status == "reuse":
        candidate = match.candidate
        if candidate is None:
            raise RuntimeError("Reusable candidate match has no candidate record")

        # A known identity may update one or both contact methods in a later registration.
        if normalized_email is not None:
            candidate.email = normalized_email
        if normalized_phone is not None:
            candidate.phone = normalized_phone
        db.flush()
        return candidate

    candidate = Candidate(
        first_name=" ".join(first_name.strip().split()),
        last_name=" ".join(last_name.strip().split()),
        email=normalized_email,
        phone=normalized_phone,
    )
    db.add(candidate)
    db.flush()
    return candidate


def anonymize_candidate(candidate: Candidate) -> None:
    """Clear identifying contact values and replace names with placeholders."""

    candidate.first_name = "Anonymized"
    candidate.last_name = "Candidate"
    candidate.email = None
    candidate.phone = None
