"""
SafeVision AI — Seed Data Script

Creates the default roles and permission matrix per the spec.
Run once after migration to populate the initial org with roles.

Usage:
    python -m app.seeds.seed_roles

This script is idempotent — safe to run multiple times.
"""

from app.database import SessionLocal
from app.models.organization import Organization
from app.models.role import Permission, Role
from app.models.user import User
from app.services.auth_service import hash_password

# ==============================================================================
# Permission Matrix (from the spec's RBAC section)
# ==============================================================================
# Every permission that exists in the system.
ALL_PERMISSIONS = [
    # Dashboard & Monitoring
    "dashboard.view",
    "monitoring.view",
    # Events
    "events.view",
    # Alerts
    "alerts.view",
    "alerts.acknowledge",
    "alerts.escalate",
    "alerts.resolve",
    # Patterns
    "patterns.view",
    "patterns.manage",
    # Reports
    "reports.export",
    # Infrastructure management
    "sites.view",
    "sites.manage",
    "zones.view",
    "zones.manage",
    "cameras.view",
    "cameras.manage",
    "rules.view",
    "rules.manage",
    # User management
    "users.view",
    "users.manage",
    "roles.manage",
    # Documents
    "documents.view",
    "documents.upload",
    "documents.delete",
    # AI / RAG
    "ai.view",
    "ai.manage",
    "rag.manage",
    # Notifications
    "notifications.view",
    "notifications.manage",
]

# Role → list of permissions it gets
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "Organization Administrator": ALL_PERMISSIONS,  # Full access
    "Safety Manager": [
        "dashboard.view", "monitoring.view",
        "events.view",
        "alerts.view", "alerts.acknowledge", "alerts.escalate", "alerts.resolve",
        "patterns.view", "patterns.manage",
        "reports.export",
        "sites.view",
        "zones.view", "zones.manage",
        "cameras.view", "cameras.manage",
        "rules.view", "rules.manage",
        "users.view",
        "documents.view", "documents.upload", "documents.delete",
        "ai.view",
        "notifications.view",
    ],
    "Safety Officer": [
        "dashboard.view", "monitoring.view",
        "events.view",
        "alerts.view", "alerts.acknowledge", "alerts.escalate",
        "patterns.view",
        "sites.view",
        "zones.view",
        "cameras.view",
        "rules.view",
        "documents.view",
        "ai.view",
        "notifications.view",
    ],
    "Operator": [
        "dashboard.view", "monitoring.view",
        "events.view",
        "alerts.view", "alerts.acknowledge",
        "patterns.view",
        "sites.view",
        "zones.view",
        "cameras.view",
        "rules.view",
        "documents.view",
        "ai.view",
        "notifications.view",
    ],
    "Viewer": [
        "dashboard.view", "monitoring.view",
        "events.view",
        "alerts.view",
        "patterns.view",
        "sites.view",
        "zones.view",
        "cameras.view",
        "documents.view",
        "ai.view",
        "notifications.view",
    ],
}


def seed_org_roles(db, org_id: str) -> dict[str, str]:
    """
    Create all default roles + permissions for an organization.
    Returns a dict of role_name → role_id.
    Idempotent: skips roles that already exist.
    """
    role_ids = {}

    for role_name, perms in ROLE_PERMISSIONS.items():
        # Check if role already exists
        existing = db.query(Role).filter(
            Role.org_id == org_id,
            Role.name == role_name,
        ).first()

        if existing:
            role_ids[role_name] = existing.id
            continue

        # Create role
        role = Role(
            name=role_name,
            description=f"Default {role_name} role",
            org_id=org_id,
        )
        db.add(role)
        db.flush()  # Get the ID

        # Create permissions
        for perm_name in perms:
            perm = Permission(
                role_id=role.id,
                perm_name=perm_name,
            )
            db.add(perm)

        role_ids[role_name] = role.id

    db.commit()
    return role_ids


def seed_demo_data():
    """
    Create a demo organization with all roles and an admin user.
    For development/testing only — not for production.
    """
    db = SessionLocal()
    try:
        # Check if demo org exists
        demo_org = db.query(Organization).filter(
            Organization.slug == "demo-org",
        ).first()

        if demo_org is None:
            demo_org = Organization(
                name="Demo Organization",
                slug="demo-org",
                description="Default development organization",
            )
            db.add(demo_org)
            db.flush()
            print(f"Created organization: {demo_org.name} (id={demo_org.id})")
        else:
            print(f"Organization already exists: {demo_org.name} (id={demo_org.id})")

        # Seed roles
        role_ids = seed_org_roles(db, demo_org.id)
        print(f"Roles seeded: {list(role_ids.keys())}")

        # Create admin user if not exists
        admin_email = "admin@safevision.local"
        admin = db.query(User).filter(User.email == admin_email).first()

        if admin is None:
            admin = User(
                org_id=demo_org.id,
                email=admin_email,
                name="System Administrator",
                pwd_hash=hash_password("admin123456"),  # noqa: S106
                role_id=role_ids["Organization Administrator"],
            )
            db.add(admin)
            db.commit()
            print(f"Created admin user: {admin_email} (password: admin123456)")
        else:
            print(f"Admin user already exists: {admin_email}")

        db.commit()
        print("\nSeed complete!")

    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_data()
