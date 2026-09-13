"""
SafeVision AI — Dashboard Statistics Schemas

Pydantic models for the dashboard summary API response.
"""

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    """Aggregated counts for the dashboard and AppHeader badge."""

    total_alerts: int = 0
    new_alerts: int = 0
    acknowledged_alerts: int = 0
    total_events: int = 0
    total_cameras: int = 0
    online_cameras: int = 0
    total_zones: int = 0
    active_zones: int = 0
