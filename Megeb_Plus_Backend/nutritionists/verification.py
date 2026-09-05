
import re
import datetime
from decimal import Decimal

# ---- Tunable configuration -------------------------------------------------

LICENSE_REGEX = re.compile(r"^LIC-[A-Z0-9\-]{3,}$", re.IGNORECASE)
FREE_EMAIL_DOMAINS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com"}
MIN_EXPERIENCE = 0
MAX_EXPERIENCE = 60          # sanity ceiling for years_of_experience
CURRENT_YEAR = datetime.date.today().year

# Weights must sum to 100. Each check contributes its weight when it passes.
WEIGHTS = {
    "completeness":   30,    # all required fields present
    "format_valid":   20,    # license/credential formats look right
    "dates_valid":    20,    # nothing expired, graduation year sane
    "consistency":    20,    # names/fields agree across the application
    "documents":      10,    # credential documents were uploaded
}

# ai_status thresholds
VERIFIED_THRESHOLD     = 85   # >= 85  -> verified (auto-clear)
NEEDS_REVIEW_THRESHOLD = 50   # 50..84 -> needs_review (admin)
                              # < 50   -> failed


# ---- Phase 2/4 hooks (return neutral results until implemented) ------------

def ocr_check(application):
    """Read license & degree docs, compare extracted text to typed values."""
    result = {"ran": False, "match_score": None, "details": {}}
    if not application.license_document:
        return result
    try:
        # --- pseudocode: call your OCR provider on the file bytes ---
        # from .ocr_provider import extract_text
        # text = extract_text(application.license_document.path)
        text = ""  # <- replace with real OCR call
        details = {}
        matches = 0
        checks = 0

        if application.license_number:
            checks += 1
            if application.license_number.strip().lower() in text.lower():
                matches += 1
                details["license_number_found"] = True
            else:
                details["license_number_found"] = False

        if application.full_name:
            checks += 1
            if application.full_name.split()[0].lower() in text.lower():
                matches += 1
                details["name_found"] = True

        result["ran"] = True
        result["match_score"] = int((matches / checks) * 100) if checks else 0
        result["details"] = details
    except Exception as exc:
        result["details"] = {"error": str(exc)}
    return result

def forgery_check(application):
    """Use a document-forensics service (or image-manipulation model).
    If suspected==True, verify_application() forces status='failed'."""
    result = {"ran": False, "suspected": False, "details": {}}
    if not application.degree_document:
        return result
    # --- integrate a tamper-detection service here ---
    # signals = forensics_provider.analyze(application.degree_document.path)
    # result["ran"] = True
    # result["suspected"] = signals["is_manipulated"]
    # result["details"] = signals
    return result

def registry_check(application):
    """Ethiopia has no public registry API today -> stays a no-op.
    When EFDA / a university exposes verification, call it here and
    set match=True/False; feed it into scoring as authoritative."""
    return {"ran": False, "match": None, "details": {"note": "no registry API available"}}

# ---- Individual rule checks ------------------------------------------------

def _check_completeness(app):
    required = [
        "full_name", "email", "phone", "specialization",
        "license_number", "license_jurisdiction", "license_expiration_date",
        "credential_type", "credential_number",
        "insurance_provider", "policy_number", "insurance_expiration_date",
        "degree", "institution", "field_of_study", "graduation_year",
    ]
    missing = [f for f in required if not getattr(app, f, None)]
    return (len(missing) == 0), {"missing_fields": missing}


def _check_format(app):
    issues = []
    if not app.license_number or not LICENSE_REGEX.match(app.license_number.strip()):
        issues.append("license_number_format")
    if app.years_of_experience is None or \
       not (MIN_EXPERIENCE <= app.years_of_experience <= MAX_EXPERIENCE):
        issues.append("years_of_experience_unrealistic")
    if app.email:
        domain = app.email.split("@")[-1].lower()
        if domain in FREE_EMAIL_DOMAINS:
            issues.append("free_email_domain")   # soft signal, not a hard fail
    return (len([i for i in issues if i != "free_email_domain"]) == 0), {"issues": issues}


def _check_dates(app):
    issues = []
    today = datetime.date.today()
    if app.license_expiration_date and app.license_expiration_date < today:
        issues.append("license_expired")
    if app.insurance_expiration_date and app.insurance_expiration_date < today:
        issues.append("insurance_expired")
    if app.graduation_year:
        if app.graduation_year > CURRENT_YEAR or app.graduation_year < 1950:
            issues.append("graduation_year_invalid")
    return (len(issues) == 0), {"issues": issues}


def _check_consistency(app):
    """Cross-field agreement. Extend as OCR (phase 2) adds extracted values."""
    issues = []
    # Related credential rows (if you populate StateLicense/DegreeCredential)
    sl = getattr(app, "state_license", None)
    if sl and sl.license_number and app.license_number:
        if sl.license_number.strip() != app.license_number.strip():
            issues.append("license_number_mismatch")
    dc = getattr(app, "degree_credential", None)
    if dc and dc.degree and app.degree:
        if dc.degree.strip().lower() != app.degree.strip().lower():
            issues.append("degree_mismatch")
    return (len(issues) == 0), {"issues": issues}


def _check_documents(app):
    docs = {
        "license_document": bool(app.license_document),
        "credential_document": bool(app.credential_document),
        "insurance_document": bool(app.insurance_document),
        "degree_document": bool(app.degree_document),
    }
    # pass if at least the license + degree documents are present
    passed = docs["license_document"] and docs["degree_document"]
    return passed, docs


# ---- Main entry point ------------------------------------------------------

def verify_application(application, persist=True):
    """Run all checks, score, set ai_status/ai_score/ai_result.
    Returns the ai_result dict. Set persist=False to compute without saving."""

    checks = {
        "completeness": _check_completeness(application),
        "format_valid": _check_format(application),
        "dates_valid":  _check_dates(application),
        "consistency":  _check_consistency(application),
        "documents":    _check_documents(application),
    }

    score = 0
    breakdown = {}
    for name, (passed, detail) in checks.items():
        weight = WEIGHTS[name]
        earned = weight if passed else 0
        score += earned
        breakdown[name] = {"passed": passed, "weight": weight,
                           "earned": earned, "detail": detail}

    # Optional layers (neutral until phases 2/4 are implemented)
    ocr = ocr_check(application)
    forgery = forgery_check(application)
    registry = registry_check(application)

    # Hard fail overrides regardless of score
    hard_fail = (
        "license_expired" in checks["dates_valid"][1].get("issues", []) or
        "license_number_format" in checks["format_valid"][1].get("issues", []) or
        forgery.get("suspected") is True
    )

    if hard_fail:
        status = "failed"
    elif score >= VERIFIED_THRESHOLD:
        status = "verified"
    elif score >= NEEDS_REVIEW_THRESHOLD:
        status = "needs_review"
    else:
        status = "failed"

    result = {
        "engine_version": "1.0-rules",
        "score": score,
        "status": status,
        "hard_fail": hard_fail,
        "breakdown": breakdown,
        "layers": {"ocr": ocr, "forgery": forgery, "registry": registry},
    }
    from .ml_scorer import ml_score
    ml = ml_score(result)
    if ml is not None:
          result["ml_score"] = ml
    # e.g. average rule score with model score once you trust it:
    score = int(round((score + ml) / 2))
    result["score"] = score
    # (re-derive status from the blended score if you like)
    if persist:
        application.ai_status = status
        application.ai_score = Decimal(str(score))
        application.ai_result = result
        application.save(update_fields=["ai_status", "ai_score", "ai_result", "updated_at"])

    return result