import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.safety_rule import SafetyRule, RuleType, RuleStatus
from app.models.user import User
from app.schemas.rule_schema import ControlsResponse, DetectionFilterUpdate, RestrictedAreaUpdate

router = APIRouter(prefix="/rules", tags=["Safety Rules"])
log = structlog.get_logger()

@router.get(
    "/controls",
    response_model=ControlsResponse,
    summary="Get Safety Controls",
    description="Get the current tenant's active detection filter and restricted area monitoring status.",
)
def get_controls(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rules = (
        db.query(SafetyRule)
        .filter(SafetyRule.org_id == current_user.org_id)
        .all()
    )

    ignored_classes = []
    restricted_area_enabled = False

    for r in rules:
        if r.rule_type.value == RuleType.CUSTOM.value and r.name == "Detection Filter":
            if r.status.value == RuleStatus.ACTIVE.value:
                ignored_classes = r.parameters.get("ignored_classes", [])
        elif r.rule_type.value == RuleType.EXCLUSION_ZONE.value:
            if r.status.value == RuleStatus.ACTIVE.value:
                restricted_area_enabled = True

    return ControlsResponse(
        ignored_classes=ignored_classes,
        restricted_area_enabled=restricted_area_enabled,
    )

@router.put(
    "/controls/detection-filter",
    response_model=ControlsResponse,
    summary="Update Detection Filter",
)
def update_detection_filter(
    payload: DetectionFilterUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Enforce RBAC - only owner/admin
    role_name = current_user.role.name.lower() if current_user.role and current_user.role.name else ""
    if role_name not in ["owner", "admin"]:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not authorized to modify safety controls")

    rule = (
        db.query(SafetyRule)
        .filter(
            SafetyRule.org_id == current_user.org_id,
            SafetyRule.rule_type == RuleType.CUSTOM,
            SafetyRule.name == "Detection Filter"
        )
        .first()
    )

    if not rule:
        rule = SafetyRule(
            org_id=current_user.org_id,
            name="Detection Filter",
            rule_type=RuleType.CUSTOM,
            parameters={"ignored_classes": payload.ignored_classes},
            status=RuleStatus.ACTIVE
        )
        db.add(rule)
    else:
        rule.parameters = {"ignored_classes": payload.ignored_classes}
        rule.status = RuleStatus.ACTIVE

    db.commit()
    return get_controls(current_user, db)

@router.put(
    "/controls/restricted-area",
    response_model=ControlsResponse,
    summary="Update Restricted Area Monitoring",
)
def update_restricted_area(
    payload: RestrictedAreaUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    role_name = current_user.role.name.lower() if current_user.role and current_user.role.name else ""
    if role_name not in ["owner", "admin"]:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Not authorized to modify safety controls")

    rule = (
        db.query(SafetyRule)
        .filter(
            SafetyRule.org_id == current_user.org_id,
            SafetyRule.rule_type == RuleType.EXCLUSION_ZONE
        )
        .first()
    )

    status = RuleStatus.ACTIVE if payload.enabled else RuleStatus.DISABLED

    if not rule:
        if payload.enabled:
            rule = SafetyRule(
                org_id=current_user.org_id,
                name="Global Restricted Area",
                rule_type=RuleType.EXCLUSION_ZONE,
                parameters={},
                status=RuleStatus.ACTIVE
            )
            db.add(rule)
    else:
        rule.status = status

    db.commit()
    return get_controls(current_user, db)
