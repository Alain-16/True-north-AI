"""
REFERENCE ONLY — Block 1C: handle_patient_event
=================================================
This is a side-by-side comparison artifact, NOT your implementation.
The real code belongs in `events/handlers.py`. Copy nothing blindly —
read it against what you wrote and port it by hand.

Imports needed in events/handlers.py (some already present there):
"""
import logging

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from core.config import get_settings
from core.database import AsyncSessionLocal          # already imported in handlers.py
from models.db import Patient                        # already imported in handlers.py
from agent.mcp_client import mcp_client              # already imported in handlers.py
# normalize_phone is the Block 1B helper, defined in the same module (handlers.py)

logger = logging.getLogger(__name__)


# --- the handler -----------------------------------------------------------

async def handle_patient_event(event: dict) -> None:
    """Sync an OpenMRS patient-created event into the local `patients` table.

    Mirrors handle_report_event's shape: fetch the resource, guard on the
    anchor field, then persist. Idempotent — safe to run on redelivered events.
    """
    resource_uuid = event["resource_uuid"]

    # The event carries only a uuid; fetch the patient to get identifier + contact.
    patient = (await mcp_client.call_tool(
        "get_patient_by_uuid", {"patient_uuid": resource_uuid}
    ))[0]

    identifier = patient.get("identifier")
    if not identifier:
        # openmrs_patient_id is the anchor every feature joins on — without it
        # the row is useless and unmatchable, so skip (don't raise).
        logger.info("Patient event %s has no identifier; skipping", resource_uuid)
        return

    settings = get_settings()
    email = patient.get("email")
    phone = normalize_phone(patient.get("phone"), settings.default_country_code)  # noqa: F821

    async with AsyncSessionLocal() as session:
        try:
            await _upsert_patient(session, identifier, email, phone)
            await session.commit()
        except IntegrityError:
            # whatsapp_phone is UNIQUE but is NOT the conflict target, so a number
            # shared by two OpenMRS patients raises here instead of being merged.
            # Retry once WITHOUT the phone so the row (and email-based web login)
            # still exists. Bounded retry — never recurses, so no infinite loop.
            await session.rollback()
            logger.warning(
                "Phone collision for openmrs_id=%s; retrying without phone", identifier
            )
            try:
                await _upsert_patient(session, identifier, email, None)
                await session.commit()
            except IntegrityError:
                await session.rollback()
                logger.exception("Could not upsert patient openmrs_id=%s", identifier)
                return

    logger.info("Synced patient %s (openmrs_id=%s)", resource_uuid, identifier)


# --- the upsert ------------------------------------------------------------

async def _upsert_patient(session, identifier: str, email: str | None,
                          phone: str | None) -> None:
    """INSERT … ON CONFLICT upsert keyed on openmrs_patient_id.

    Enrich-never-regress semantics:
      * status is set only on first insert; a redelivery does NOT reset a
        patient who has since linked a channel.
      * COALESCE(excluded, existing) means a later event with null contact
        never wipes a value we already captured (new data wins, null never does).
    """
    stmt = pg_insert(Patient).values(
        openmrs_patient_id=identifier,
        web_email=email,
        whatsapp_phone=phone,
        status="pending_channel_link",
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["openmrs_patient_id"],
        set_={
            "web_email": func.coalesce(stmt.excluded.web_email, Patient.web_email),
            "whatsapp_phone": func.coalesce(
                stmt.excluded.whatsapp_phone, Patient.whatsapp_phone
            ),
            "updated_at": func.now(),
            # NOTE: 'status' intentionally omitted — never regress on redelivery.
        },
    )
    await session.execute(stmt)


# ===========================================================================
# REFERENCE ONLY — Block 1D: consumer wiring (event routing)
# ===========================================================================
# Three surgical edits across two existing files. Shown together here; port
# each into its real home by hand.

# ---------------------------------------------------------------------------
# events/handlers.py  — edit 1 of 2: register the patient topic
# ---------------------------------------------------------------------------
TOPIC_RESOURCE_TYPE = {
    "/topic/CREATED:org.openmrs.Obs":       "lab",
    "/topic/CREATED:org.openmrs.DrugOrder": "prescription",
    "/topic/CREATED:org.openmrs.Patient":   "patient",   # NEW — confirmed live topic
}
# Double duty: this also drives DESTINATIONS (subscriptions) in the consumer,
# and parse_event already reads `uuid` generically, so no change to parse_event.


# ---------------------------------------------------------------------------
# events/handlers.py  — edit 2 of 2: the dispatch map
# Place this AFTER both handle_report_event and handle_patient_event are defined
# (the dict literal binds the function objects when it executes).
# ---------------------------------------------------------------------------
EVENT_HANDLERS = {
    "lab":          handle_report_event,      # noqa: F821  (defined above in handlers.py)
    "prescription": handle_report_event,      # noqa: F821
    "patient":      handle_patient_event,     # two topics legitimately share a handler
}


# ---------------------------------------------------------------------------
# events/activemq_consumer.py  — edit 3 of 2 (the consumer side)
#   * import EVENT_HANDLERS instead of handle_report_event
#   * dispatch by resource_type in on_message
#   * generalize the failure-log message (no longer always the report handler)
# ---------------------------------------------------------------------------
#
#   from events.handlers import TOPIC_RESOURCE_TYPE, EVENT_HANDLERS, parse_event
#
def _log_future_error(fut) -> None:
    try:
        fut.result()
    except Exception:
        logger.exception("event handler failed")     # was "handle_report_event failed"


# (method on ReportEventListener)
def on_message(self, frame) -> None:
    event = parse_event(frame.headers.get("destination", ""), frame.body)
    if event is None:
        return
    # Route by type. Unknown types (a subscribed topic with no handler) are a
    # silent no-op, never a crash.
    handler = EVENT_HANDLERS.get(event["resource_type"])     # noqa: F821
    if handler is None:
        return
    # run_coroutine_threadsafe hands the coroutine to the APP event loop — required
    # because handle_patient_event does async DB work via AsyncSessionLocal, which
    # must run on that loop, not on this STOMP listener thread.
    fut = asyncio.run_coroutine_threadsafe(handler(event), self._loop)   # noqa: F821
    fut.add_done_callback(_log_future_error)


# ===========================================================================
# REFERENCE ONLY — Block 2A: generate + store the OTP
# ===========================================================================
# Real home: features/auth/service.py
# Plus two config fields in core/config.py:
#     resend_api_key: str
#     email_from: str = "MediAgent <noreply@yourdomain.com>"

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from core.config import get_settings
from models.db import OTPToken


async def generate_otp(session, phone: str, purpose: str) -> str:
    """Create a fresh single-use OTP for (phone, purpose); return the plaintext code.

    Invalidates any prior unused codes first, so only the newest is ever valid —
    which also keeps the `idx_otp_phone_purpose WHERE NOT used` partial index
    pointing at a single active row. Runs inside the caller's transaction; the
    caller commits (so invalidate + insert land atomically with the rest of the
    request).
    """
    settings = get_settings()

    # Kill any still-live codes for this (phone, purpose) before issuing a new one.
    # `.is_(False)` mirrors the index predicate `WHERE NOT used`.
    await session.execute(
        update(OTPToken)
        .where(
            OTPToken.phone == phone,
            OTPToken.purpose == purpose,
            OTPToken.used.is_(False),
        )
        .values(used=True)
    )

    # CSPRNG (not `random`); zero-padded so a code like 042315 keeps all 6 digits
    # and fits the fixed-width VARCHAR(6) column.
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.otp_expiry_minutes)

    # session.add is synchronous (no await) — it just stages the INSERT.
    session.add(OTPToken(phone=phone, token=code, purpose=purpose, expires_at=expires_at))

    return code


# ===========================================================================
# REFERENCE ONLY — Block 2B: verify the OTP
# ===========================================================================
# Real home: features/auth/service.py (same module as generate_otp).
# Already imported above for 2A: secrets, datetime/timezone, OTPToken.
# Add: from sqlalchemy import select

async def verify_otp(session, phone: str, purpose: str, submitted_code: str | None) -> bool:
    """Validate a submitted OTP. Returns True only for the current, live, unused
    code, and burns it (marks used) on success so it can't be replayed.

    Does NOT commit — the caller (Block 3 verify endpoint) commits after issuing
    tokens, so "code consumed" and "tokens issued" land atomically.
    """
    # Gate 1: fetch the newest active code. 2A guarantees one, but order_by+limit(1)
    # is cheap insurance against stale duplicates.
    row = (await session.execute(
        select(OTPToken)
        .where(
            OTPToken.phone == phone,
            OTPToken.purpose == purpose,
            OTPToken.used.is_(False),
        )
        .order_by(OTPToken.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    # Gate 2: none issued / already used. Don't tell the caller which.
    if row is None:
        return False

    # Gate 3: expired. Both sides tz-aware (TIMESTAMPTZ + UTC now).
    if row.expires_at <= datetime.now(timezone.utc):
        return False

    # Gate 4: constant-time compare. Guard empty input first (compare_digest needs
    # two real strings); `==` would short-circuit and leak timing per character.
    if not submitted_code or not secrets.compare_digest(row.token, submitted_code):
        # Deliberately do NOT mark used on failure — that would let an attacker
        # DoS a victim's code. (Brute-force protection is the deferred attempts-cap.)
        return False

    # Success: burn the code. row is already persistent — the mutation is tracked,
    # no session.add needed. Caller commits.
    row.used = True
    return True


# ===========================================================================
# REFERENCE ONLY — Block 2C: email delivery (Resend)
# ===========================================================================
# Real home: features/auth/email.py  (its own module = the provider boundary is
# obvious; swapping to SendGrid/SES later is a one-file change).
# Prereq: resend_api_key + email_from in config; email_from must be a VERIFIED
# sender/domain in the Resend dashboard or sends 4xx.

import logging

import httpx

from core.config import get_settings

logger = logging.getLogger(__name__)

_RESEND_URL = "https://api.resend.com/emails"


async def send_otp_email(to_email: str, code: str) -> None:
    """POST a verification email to Resend. Raises on failure — the caller (2D)
    catches/logs and still returns a generic response (anti-enumeration).

    NEVER log `code`: it's a live secret. Log the address + status only.
    """
    if not to_email:
        raise ValueError("send_otp_email called with no recipient")

    settings = get_settings()
    payload = {
        "from": settings.email_from,
        "to": [to_email],                       # Resend expects an array
        "subject": "Your MediAgent verification code",
        "text": (
            f"Your verification code is {code}. "
            f"It expires in {settings.otp_expiry_minutes} minutes."
        ),
    }
    headers = {"Authorization": f"Bearer {settings.resend_api_key}"}

    # Per-call client is fine at OTP volume. Timeout is mandatory — a hung Resend
    # connection would otherwise hang the patient's login request indefinitely.
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(_RESEND_URL, json=payload, headers=headers)
        resp.raise_for_status()                 # let 4xx/5xx + transport errors propagate

    logger.info("OTP email sent to %s (status %s)", to_email, resp.status_code)


# ===========================================================================
# REFERENCE ONLY — Block 2D: orchestration + POST /auth/request-otp
# ===========================================================================

# ---------------------------------------------------------------------------
# Prereq refactor: move normalize_phone (Block 1B) to a SHARED module so sync
# and login normalize identically. Real home: core/phone.py
#   from core.phone import normalize_phone
# Then events/handlers.py imports it from there too (delete the local copy).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# features/auth/schemas.py
# ---------------------------------------------------------------------------
from pydantic import BaseModel, EmailStr      # EmailStr needs `email-validator` installed


class RequestOTP(BaseModel):
    phone: str
    email: EmailStr


# ---------------------------------------------------------------------------
# features/auth/service.py — the orchestrator
#   from sqlalchemy import select, func
#   from core.phone import normalize_phone
#   from models.db import Patient
#   (generate_otp / send_otp_email already in this feature package)
# ---------------------------------------------------------------------------
async def request_login_otp(session, phone: str, email: str) -> None:
    """Look up a patient by normalized phone AND (case-insensitive) email, and
    only if found, issue + email a web_login OTP. Silent on no-match — the route
    is what keeps the response uniform (anti-enumeration).
    """
    settings = get_settings()
    norm_phone = normalize_phone(phone, settings.default_country_code)   # noqa: F821

    patient = (await session.execute(
        select(Patient).where(                                          # noqa: F821
            Patient.whatsapp_phone == norm_phone,                       # noqa: F821
            func.lower(Patient.web_email) == email.lower(),             # noqa: F821
        )
    )).scalar_one_or_none()

    # No match, or matched but has no email on file -> do nothing. Route still
    # returns the generic response, so the caller can't tell the difference.
    if patient is None or not patient.web_email:
        logger.info("request_login_otp: no eligible patient for given phone/email")
        return

    code = await generate_otp(session, patient.whatsapp_phone, "web_login")  # noqa: F821

    # SEND before COMMIT: if the email fails, the uncommitted transaction rolls
    # back, so we never persist a code we couldn't deliver — and we don't
    # invalidate the user's previous still-valid code.
    await send_otp_email(patient.web_email, code)                        # noqa: F821
    await session.commit()


# ---------------------------------------------------------------------------
# features/auth/router.py
#   from fastapi import APIRouter, Depends
#   from sqlalchemy.ext.asyncio import AsyncSession
#   from core.database import get_db
#   from features.auth.schemas import RequestOTP
#   from features.auth.service import request_login_otp
# ---------------------------------------------------------------------------
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

_GENERIC_OTP_RESPONSE = {"message": "If those details match an account, a code has been sent."}


@router.post("/request-otp")
async def request_otp(body: RequestOTP, session: AsyncSession = Depends(get_db)):  # noqa: F821
    try:
        await request_login_otp(session, body.phone, body.email)
    except Exception:
        # Email/transport/db failure — record it, but stay opaque to the client.
        # (get_db closes the session; the uncommitted tx rolls back.)
        logger.exception("request-otp failed for submitted details")
    # ALWAYS the same response: found / not-found / email-failed are identical.
    return _GENERIC_OTP_RESPONSE


# ---------------------------------------------------------------------------
# main.py — wiring (name clash: chat already imports `router`, so alias)
# ---------------------------------------------------------------------------
#   from features.auth.router import router as auth_router
#   app.include_router(auth_router)        # path becomes POST /auth/request-otp


# ===========================================================================
# REFERENCE ONLY — Block 3A: deps, config, refresh_tokens table
# ===========================================================================

# ---------------------------------------------------------------------------
# requirements.txt
# ---------------------------------------------------------------------------
#   PyJWT
#   (email-validator   <- from Block 2D, if not added yet)

# ---------------------------------------------------------------------------
# core/config.py — add to Settings
# ---------------------------------------------------------------------------
#   jwt_secret_key: str                       # from .env, NO default (it's a secret)
#   jwt_algorithm: str = "HS256"              # symmetric: FastAPI both signs & verifies
#   access_token_expire_minutes: int = 15     # short — limits a leaked access token
#   refresh_token_expire_days: int = 7        # long — user isn't forced to re-login
#
# Generate the secret once:  python -c "import secrets; print(secrets.token_urlsafe(64))"
# Put it in .env as JWT_SECRET_KEY=...  (never commit it)


# ---------------------------------------------------------------------------
# models/db.py — new model (mirrors your existing style)
# ---------------------------------------------------------------------------
class RefreshToken(Base):                                   # noqa: F821
    __tablename__ = "refresh_tokens"

    # id IS the jti embedded in the refresh JWT — the row is the source of truth;
    # we never store the token string (the signature proves authenticity).
    id          = sa.Column(sa.Uuid, primary_key=True, server_default=sa.text("gen_random_uuid()"))   # noqa: F821
    patient_id  = sa.Column(sa.Uuid, sa.ForeignKey("patients.id"), nullable=False)                    # noqa: F821
    expires_at  = sa.Column(sa.DateTime(timezone=True), nullable=False)                                # noqa: F821
    revoked     = sa.Column(sa.Boolean, nullable=False, server_default=sa.text("FALSE"))               # noqa: F821
    # Audit/reuse chain: which token rotated this one. Optional — drop if the
    # self-FK fights Alembic and you want to keep MVP simple.
    replaced_by_id = sa.Column(sa.Uuid, sa.ForeignKey("refresh_tokens.id"))                            # noqa: F821
    created_at  = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()"))  # noqa: F821
    last_used_at = sa.Column(sa.DateTime(timezone=True))                                               # noqa: F821

    __table_args__ = (
        sa.Index("idx_refresh_patient", "patient_id"),                                                # noqa: F821
    )


# ---------------------------------------------------------------------------
# Migration:  alembic revision --autogenerate -m "add refresh_tokens"
#   then REVIEW the generated file (autogenerate can miss server_default / the
#   self-FK may need use_alter). Hand-written equivalent in your medical_profiles
#   migration style:
#
#   def upgrade():
#       op.create_table(
#           "refresh_tokens",
#           sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
#           sa.Column("patient_id", sa.Uuid(), nullable=False),
#           sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
#           sa.Column("revoked", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False),
#           sa.Column("replaced_by_id", sa.Uuid(), nullable=True),
#           sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
#           sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
#           sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
#           sa.ForeignKeyConstraint(["replaced_by_id"], ["refresh_tokens.id"], use_alter=True),
#           sa.PrimaryKeyConstraint("id"),
#       )
#       op.create_index("idx_refresh_patient", "refresh_tokens", ["patient_id"])
#
#   def downgrade():
#       op.drop_index("idx_refresh_patient", table_name="refresh_tokens")
#       op.drop_table("refresh_tokens")


# ===========================================================================
# REFERENCE ONLY — Block 3B: core/security.py (JWT helpers)
# ===========================================================================
# Pure functions: no DB, no FastAPI. Easiest block to unit-test.

import jwt                                          # PyJWT
from datetime import datetime, timedelta, timezone

from core.config import get_settings


def create_access_token(patient_id: str, openmrs_patient_id: str) -> str:
    """Short-lived token used on every request. Carries identity so middleware
    can authorize from the signature alone — no DB hit."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(patient_id),                     # JWT spec: sub must be a string
        "openmrs_patient_id": openmrs_patient_id,
        "type": "access",                           # typed: refresh tokens can't pass here
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(jti: str, patient_id: str) -> str:
    """Long-lived token whose ONLY job is to mint access tokens. `jti` is the
    refresh_tokens row id that 3D looks up for rotation/revocation."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(patient_id),
        "type": "refresh",
        "jti": str(jti),
        "iat": now,
        "exp": now + timedelta(days=settings.refresh_token_expire_days),
    }
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_type: str) -> dict:
    """Verify signature + expiry (jwt.decode does both) and enforce the token
    type. Raises jwt.InvalidTokenError (or a subclass: ExpiredSignatureError,
    DecodeError) on any failure — callers catch that one family and return 401.
    """
    settings = get_settings()
    # algorithms MUST be an explicit list — never let the token header choose
    # (the 'alg confusion' / 'none' attack).
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("wrong token type")
    return payload


# ===========================================================================
# REFERENCE ONLY — Block 3C: POST /auth/verify-otp (verify -> issue pair)
# ===========================================================================

# ---------------------------------------------------------------------------
# features/auth/schemas.py  (add to the file with RequestOTP)
# ---------------------------------------------------------------------------
class VerifyOTP(BaseModel):                         # noqa: F821
    phone: str
    code: str


class TokenPair(BaseModel):                          # noqa: F821
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# features/auth/router.py  (add to the auth router)
#   import uuid
#   from datetime import datetime, timedelta, timezone
#   from fastapi import HTTPException
#   from sqlalchemy import select
#   from core.config import get_settings
#   from core.phone import normalize_phone
#   from core.security import create_access_token, create_refresh_token
#   from models.db import Patient, RefreshToken
#   from features.auth.service import verify_otp
# ---------------------------------------------------------------------------
@router.post("/verify-otp", response_model=TokenPair)               # noqa: F821
async def verify_otp_endpoint(body: VerifyOTP,                        # noqa: F821
                              session: AsyncSession = Depends(get_db)):  # noqa: F821
    settings = get_settings()
    norm_phone = normalize_phone(body.phone, settings.default_country_code)   # noqa: F821

    # Generic 401 for EVERY failure — no distinguishing bad-phone from bad-code.
    bad = HTTPException(status_code=401, detail="Invalid or expired code")    # noqa: F821

    # Identify the patient FIRST — verifying before we know we can build claims
    # would burn a code for an unusable login.
    patient = (await session.execute(
        select(Patient).where(Patient.whatsapp_phone == norm_phone)           # noqa: F821
    )).scalar_one_or_none()
    if patient is None:
        raise bad

    if not await verify_otp(session, norm_phone, "web_login", body.code):     # noqa: F821
        raise bad

    # Past both gates: mint the pair. Generate jti in Python so we know the id
    # before the insert (no flush round-trip needed to embed it in the JWT).
    jti = uuid.uuid4()                                                        # noqa: F821
    refresh_exp = datetime.now(timezone.utc) + timedelta(                     # noqa: F821
        days=settings.refresh_token_expire_days
    )

    access = create_access_token(patient.id, patient.openmrs_patient_id)      # noqa: F821
    refresh = create_refresh_token(jti, patient.id)                           # noqa: F821

    session.add(RefreshToken(id=jti, patient_id=patient.id, expires_at=refresh_exp))  # noqa: F821

    # ONE commit — verify_otp's `used=True` and the new RefreshToken row land
    # together. Atomic: both or neither.
    await session.commit()

    return TokenPair(access_token=access, refresh_token=refresh)
