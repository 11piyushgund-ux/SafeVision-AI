import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Bell, Eye, LogOut, Settings } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { fetchDashboardSummary } from "@/lib/api-client";
import { getAuthToken } from "@/lib/api-client";

export function AppHeader() {
  const { user, logout } = useAuth();

  // Only fetch stats if the user is authenticated (has a token)
  const { data: stats } = useQuery({
    queryKey: ["dashboard-summary"],
    queryFn: fetchDashboardSummary,
    enabled: !!getAuthToken(),
    refetchInterval: 30_000,
    // Don't show errors for the badge - just show 0
    retry: false,
  });

  const unreadAlertCount = stats?.new_alerts ?? 0;

  return (
    <header className="border-b border-border bg-card">
      <div className="mx-auto flex max-w-[1560px] items-center justify-between gap-4 px-6 py-3">
        <Link to="/" className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand text-primary-foreground">
            <Eye className="h-5 w-5" />
          </div>
          <div className="leading-tight">
            <p className="text-xl font-bold tracking-tight">
              SafeVision <span className="text-brand">AI</span>
            </p>
            <p className="text-[10px] font-semibold tracking-[0.14em] text-muted-foreground">
              SAFETY INTELLIGENCE PLATFORM
            </p>
          </div>
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          <Link
            to="/live-monitoring"
            activeProps={{ className: "bg-accent text-foreground" }}
            className="rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent"
          >
            Live Monitoring
          </Link>
          <Link
            to="/alerts"
            activeProps={{ className: "bg-accent text-foreground" }}
            className="rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent"
          >
            Safety Alerts
          </Link>
          <Link
            to="/patterns"
            activeProps={{ className: "bg-accent text-foreground" }}
            className="rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent"
          >
            Recurring Patterns
          </Link>
          <Link
            to="/ai-safety-insights"
            activeProps={{ className: "bg-accent text-foreground" }}
            className="rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent"
          >
            AI Safety Insights
          </Link>
          <Link
            to="/event-history"
            activeProps={{ className: "bg-accent text-foreground" }}
            className="rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent"
          >
            Event History
          </Link>
          <Link
            to="/documents"
            activeProps={{ className: "bg-accent text-foreground" }}
            className="rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent"
          >
            Safety Management
          </Link>
        </nav>


        <div className="flex items-center gap-4">
          <span className="hidden items-center gap-2 rounded-full bg-safe-soft px-4 py-2 text-xs font-semibold tracking-wide text-safe sm:inline-flex">
            <span className="h-2 w-2 rounded-full bg-safe" />
            AI MONITORING ACTIVE
          </span>
          <button className="relative rounded-lg p-2 text-muted-foreground transition-colors hover:bg-accent">
            <Bell className="h-5 w-5" />
            {unreadAlertCount > 0 && (
              <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-danger text-[10px] font-bold text-primary-foreground">
                {unreadAlertCount}
              </span>
            )}
          </button>
          <Link
            to="/settings"
            activeProps={{ className: "bg-accent text-foreground" }}
            className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-accent"
          >
            <Settings className="h-5 w-5" />
          </Link>
          {user && (
            <span className="hidden text-sm font-medium text-muted-foreground lg:inline">
              {user.name}
            </span>
          )}
          <button
            type="button"
            onClick={logout}
            className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-medium transition-colors hover:bg-accent"
          >
            <LogOut className="h-4 w-4" />
            Logout
          </button>
        </div>
      </div>
    </header>
  );
}
