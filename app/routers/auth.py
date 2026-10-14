import os
import hmac
import secrets
import hashlib
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.database import get_db
from backend.app.models.entities import Manager, ManagerOTP
from backend.app.schemas.schemas import (
    LoginRequest,
    TokenResponse,
    ManagerOut,
    SendOtpRequest,
    SendOtpResponse,
    VerifyOtpRequest,
)
from backend.app.auth.security import verify_password, create_access_token
from backend.app.auth.dependencies import get_current_manager
from backend.app.services.email_service import (
    is_smtp_configured,
    send_otp_email,
    EmailConfigMissingException,
    EmailDeliveryException,
    mask_email,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
logger = logging.getLogger("talentmatch.auth")


def hash_otp_code(otp_code: str, manager_id: int) -> str:
    """Cryptographically secure constant salt hash for storing/verifying OTPs."""
    salt = os.getenv("JWT_SECRET", "talentmatch-super-secret-jwt-key-2026-campus-recruitment")
    return hashlib.sha256(f"{otp_code.strip()}:{manager_id}:{salt}".encode("utf-8")).hexdigest()


@router.post("/send-otp", response_model=SendOtpResponse)
def send_otp(payload: SendOtpRequest, db: Session = Depends(get_db)):
    """
    Generates a secure, random 6-digit OTP and delivers it to the manager's registered email via SMTP.
    Enforces registered manager verification, 60s resend cooldown, 5-attempt limits, and invalidates previous OTPs.
    """
    clean_email = str(payload.email).strip().lower()
    logger.info(f"OTP generation requested for manager: {mask_email(clean_email)}")

    # 1. Verify that manager is registered in database
    manager = db.query(Manager).filter(func.lower(Manager.email) == clean_email).first()
    if not manager:
        logger.warning(f"OTP request rejected: unregistered email {mask_email(clean_email)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No manager account found with this email address. Please use your registered manager email."
        )

    # 2. Verify that SMTP email service is configured
    if not is_smtp_configured():
        logger.warning("OTP generation rejected: SMTP configuration is missing or incomplete.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service is not configured. Please set SMTP_HOST, SMTP_PORT, SMTP_USER, and SMTP_PASSWORD in .env."
        )

    now = datetime.utcnow()

    # 2. Check Resend Cooldown (60 seconds)
    recent_otp = db.query(ManagerOTP).filter(
        ManagerOTP.manager_id == manager.id,
        ManagerOTP.is_used == False,
        ManagerOTP.expires_at > now
    ).order_by(ManagerOTP.created_at.desc()).first()

    if recent_otp:
        elapsed = (now - recent_otp.created_at).total_seconds()
        if elapsed < 60:
            remaining = max(1, int(60 - elapsed))
            logger.info(f"Cooldown active for manager ID={manager.id}: {remaining}s remaining")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {remaining} second(s) before requesting a new OTP. Cooldown in progress."
            )

    # 3. Burst Rate Limiting (max 5 requests per 15 minutes)
    window_start = now - timedelta(minutes=15)
    recent_requests_count = db.query(ManagerOTP).filter(
        ManagerOTP.manager_id == manager.id,
        ManagerOTP.created_at >= window_start
    ).count()

    if recent_requests_count >= 5:
        logger.warning(f"Burst rate limit reached for manager ID={manager.id} ({recent_requests_count} requests in 15m)")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many verification requests in a short time. Please wait 15 minutes before requesting again."
        )

    # 4. Generate Cryptographically Secure 6-digit OTP
    raw_otp = f"{secrets.randbelow(900000) + 100000:06d}"
    otp_hash = hash_otp_code(raw_otp, manager.id)
    expires_at = now + timedelta(minutes=5)

    # 5. Invalidate all previous unused OTPs for this manager (prevents reuse and ensures single active OTP)
    db.query(ManagerOTP).filter(
        ManagerOTP.manager_id == manager.id,
        ManagerOTP.is_used == False
    ).update({"is_used": True})

    # 6. Create new OTP record
    otp_record = ManagerOTP(
        manager_id=manager.id,
        email=manager.email,
        otp_hash=otp_hash,
        created_at=now,
        expires_at=expires_at,
        is_used=False,
        attempts=0
    )
    db.add(otp_record)
    db.commit()
    db.refresh(otp_record)

    # 7. Deliver OTP via Email
    try:
        send_otp_email(to_email=manager.email, manager_name=manager.name, otp_code=raw_otp)
    except EmailConfigMissingException as exc:
        otp_record.is_used = True
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc)
        )
    except EmailDeliveryException as exc:
        otp_record.is_used = True
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc)
        )
    except Exception as exc:
        otp_record.is_used = True
        db.commit()
        logger.error(f"Unexpected error transmitting OTP email: {str(exc)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deliver verification code due to an unexpected email server error."
        )

    return SendOtpResponse(
        message="Verification code sent to your registered email address.",
        email=manager.email,
        expires_in_seconds=300,
        cooldown_seconds=60
    )


@router.post("/verify-otp", response_model=TokenResponse)
def verify_otp(payload: VerifyOtpRequest, db: Session = Depends(get_db)):
    """
    Verifies the 6-digit OTP code.
    Validates expiration (5 minutes), attempt limit (max 5), and single-use policy.
    Issues a JWT access token on success.
    """
    clean_email = str(payload.email).strip().lower()
    clean_otp = str(payload.otp).strip()

    if not clean_otp.isdigit() or len(clean_otp) != 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code must be exactly 6 numeric digits."
        )

    manager = db.query(Manager).filter(func.lower(Manager.email) == clean_email).first()
    if not manager:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manager account not found."
        )

    now = datetime.utcnow()

    # Fetch latest active OTP record for this manager
    otp_record = db.query(ManagerOTP).filter(
        ManagerOTP.manager_id == manager.id,
        ManagerOTP.is_used == False
    ).order_by(ManagerOTP.created_at.desc()).first()

    if not otp_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active verification code found or this code has already been used. Please request a new OTP."
        )

    # Expiry Check (5 minutes)
    if now > otp_record.expires_at:
        otp_record.is_used = True
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This verification code has expired (5-minute limit exceeded). Please request a new OTP."
        )

    # Attempts Check
    if otp_record.attempts >= 5:
        otp_record.is_used = True
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum verification attempts exceeded. This OTP has been invalidated. Please request a new code."
        )

    # Constant-time comparison
    expected_hash = hash_otp_code(clean_otp, manager.id)
    if not hmac.compare_digest(otp_record.otp_hash, expected_hash):
        otp_record.attempts += 1
        if otp_record.attempts >= 5:
            otp_record.is_used = True
        db.commit()

        remaining = max(0, 5 - otp_record.attempts)
        if remaining == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect verification code. Maximum attempts exceeded and code has been invalidated. Please request a new OTP."
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Incorrect verification code. {remaining} attempt(s) remaining."
        )

    # Invalidate OTP on successful use to prevent reuse
    otp_record.is_used = True
    db.commit()

    # Generate JWT access token
    token = create_access_token(subject=manager.id)
    logger.info(f"Successful OTP verification login for manager: {mask_email(manager.email)} (ID: {manager.id})")
    return {
        "access_token": token,
        "token_type": "bearer",
        "manager": ManagerOut.model_validate(manager)
    }


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Standard password authentication endpoint preserved for system compatibility.
    """
    clean_email = payload.email.strip().lower()
    logger.info(f"Manager password login attempt for email: {mask_email(clean_email)}")
    manager = db.query(Manager).filter(func.lower(Manager.email) == clean_email).first()

    if not manager or not verify_password(payload.password, manager.password_hash):
        logger.warning(f"Failed password login attempt for: {mask_email(clean_email)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid manager credentials. Please check your email and password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(subject=manager.id)
    logger.info(f"Successful password login for manager: {mask_email(manager.email)} (ID: {manager.id})")
    return {
        "access_token": token,
        "token_type": "bearer",
        "manager": ManagerOut.model_validate(manager)
    }


@router.post("/logout")
def logout(current_manager: Manager = Depends(get_current_manager)):
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=ManagerOut)
def get_me(current_manager: Manager = Depends(get_current_manager)):
    return ManagerOut.model_validate(current_manager)
