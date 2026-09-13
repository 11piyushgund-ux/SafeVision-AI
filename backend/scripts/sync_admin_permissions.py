"""
Sync notifications.view and notifications.manage permissions to all Admin
and Organization Administrator roles in PostgreSQL.
"""
import os, sys, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine
from sqlalchemy import text

NEW_PERMS = ["notifications.view", "notifications.manage"]

with engine.begin() as conn:
    roles = conn.execute(text("""
        SELECT id, name, org_id FROM roles
        WHERE name IN ('Admin', 'Organization Administrator')
    """)).fetchall()

    print(f"Found {len(roles)} admin roles to synchronize.")
    total_added = 0

    for r in roles:
        role_id = r[0]
        existing = {
            row[0] for row in conn.execute(
                text("SELECT perm_name FROM permissions WHERE role_id = :rid"),
                {"rid": role_id}
            ).fetchall()
        }

        for perm in NEW_PERMS:
            if perm not in existing:
                conn.execute(text("""
                    INSERT INTO permissions (id, role_id, perm_name)
                    VALUES (:id, :rid, :pname)
                """), {"id": str(uuid.uuid4()), "rid": role_id, "pname": perm})
                total_added += 1

    print(f"[OK] Successfully added {total_added} missing permission records across admin roles.")

    # Verify test user role specifically
    test_user_role = conn.execute(text("""
        SELECT u.email, r.name, p.perm_name
        FROM users u
        JOIN roles r ON u.role_id = r.id
        JOIN permissions p ON r.id = p.role_id
        WHERE u.email = 'testmail@gmail.com' AND p.perm_name LIKE 'notifications.%'
    """)).fetchall()
    print("\nVerified permissions for 'testmail@gmail.com':")
    for row in test_user_role:
        print(f"  {row[0]} ({row[1]}): {row[2]}")
