import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import {
  Bell,
  Calendar,
  CheckCircle2,
  Clock,
  Globe,
  Info,
  LayoutDashboard,
  List,
  Loader2,
  Mail,
  MessageCircle,
  RefreshCw,
  Save,
  Settings as SettingsIcon,
  Sun,
  X,
  ShieldAlert,
  AlertCircle,
} from "lucide-react";
import { AppHeader } from "@/components/AppHeader";
import { AuthGuard } from "@/components/auth-guard";
import { Switch } from "@/components/ui/switch";
import {
  getSafetyControls,
  updateDetectionFilter,
  fetchNotificationSettings,
  saveNotificationSettings,
} from "@/lib/api-client";
import {
  AUTO_REFRESH_OPTIONS_SECONDS,
  DATE_FORMAT_LABELS,
  DEFAULT_DASHBOARD_LABELS,
  DEFAULT_NOTIFICATION_PREFERENCES,
  DEFAULT_USER_SETTINGS,
  ITEMS_PER_PAGE_OPTIONS,
  LANGUAGE_LABELS,
  THEME_LABELS,
  TIME_FORMAT_LABELS,
  type AppLanguage,
  type AppTheme,
  type DateFormat,
  type DefaultDashboard,
  type NotificationChannel,
  type NotificationPreferences,
  type SettingsSection,
  type TimeFormat,
  type UserSettings,
} from "@/lib/safety-types";

export const Route = createFileRoute("/settings")({
  head: () => ({
    meta: [
      { title: "Settings | SafeVision AI" },
      {
        name: "description",
        content:
          "Manage SafeVision AI system preferences, dashboard defaults and safety notification channels.",
      },
      { property: "og:title", content: "Settings | SafeVision AI" },
      {
        property: "og:description",
        content: "Application preferences, dashboard defaults and notification channels.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: SettingsPage,
});

const selectClass =
  "w-full appearance-none rounded-lg border border-border bg-background py-2.5 pl-10 pr-8 text-sm font-medium outline-none focus:border-brand";

function Row({
  label,
  description,
  children,
}: {
  label: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid items-center gap-3 border-b border-border/60 py-4 last:border-0 md:grid-cols-[1fr_380px]">
      <div>
        <p className="text-sm font-semibold">{label}</p>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      <div className="relative">{children}</div>
    </div>
  );
}

function SettingsPage() {
  const [section, setSection] = useState<SettingsSection>("general");
  const [settings, setSettings] = useState<UserSettings>(DEFAULT_USER_SETTINGS);
  const [prefs, setPrefs] = useState<NotificationPreferences>(
    DEFAULT_NOTIFICATION_PREFERENCES,
  );
  const [savedMessage, setSavedMessage] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [notifSaving, setNotifSaving] = useState(false);
  const [notifLoading, setNotifLoading] = useState(false);

  // --- Notification-specific backend state (Phase 18 Dual Channel) ---
  const [notifEnabled, setNotifEnabled] = useState(false);
  const [notifMode, setNotifMode] = useState<"email" | "whatsapp">("email");
  const [emailRecipient, setEmailRecipient] = useState("");
  const [whatsappRecipient, setWhatsappRecipient] = useState("");

  const [ignoredClasses, setIgnoredClasses] = useState<string[]>([]);
  const [controlsLoading, setControlsLoading] = useState(true);

  // Load safety controls
  useEffect(() => {
    getSafetyControls()
      .then((res) => {
        setIgnoredClasses(res.ignored_classes);
        setControlsLoading(false);
      })
      .catch((err) => {
        console.error("Failed to load safety controls", err);
        setControlsLoading(false);
      });
  }, []);

  // Load org notification settings from backend on mount
  useEffect(() => {
    setNotifLoading(true);
    fetchNotificationSettings()
      .then((s) => {
        setNotifEnabled(s.notifications_enabled);
        setNotifMode(s.notification_mode);
        const resolvedEmail = s.email_recipient ?? (s.notification_mode === "email" && s.notification_recipient && s.notification_recipient.includes("@") ? s.notification_recipient : "");
        const resolvedWa = s.whatsapp_recipient ?? (s.notification_mode === "whatsapp" && s.notification_recipient && !s.notification_recipient.includes("@") ? s.notification_recipient : "");
        setEmailRecipient(resolvedEmail);
        setWhatsappRecipient(resolvedWa);
        // Keep prefs in sync for legacy display fields
        setPrefs((p) => ({
          ...p,
          notification_channel: s.notification_mode,
          email_address: resolvedEmail || p.email_address,
          whatsapp_number: resolvedWa || p.whatsapp_number,
        }));
      })
      .catch(() => {
        // Non-fatal — page still usable, defaults apply
      })
      .finally(() => setNotifLoading(false));
  }, []);

  async function handleToggleClass(className: string) {
    const isIgnored = ignoredClasses.includes(className);
    const newIgnored = isIgnored
      ? ignoredClasses.filter((c) => c !== className)
      : [...ignoredClasses, className];
    
    // Optimistic update
    setIgnoredClasses(newIgnored);
    
    try {
      const res = await updateDetectionFilter({ ignored_classes: newIgnored });
      setIgnoredClasses(res.ignored_classes);
      setSavedMessage(`Detection filter updated.`);
    } catch (err) {
      console.error("Update failed", err);
      // Revert on error
      setIgnoredClasses(ignoredClasses);
    }
  }

  /** Replace with an update on `user_settings` / `notification_preferences`. */
  function handleSave(message: string) {
    setSavedMessage(message);
  }

  async function handleSaveNotifications() {
    setSavedMessage(null);
    setSaveError(null);

    const cleanEmail = emailRecipient.trim();
    const cleanWa = whatsappRecipient.trim();

    // Validate email format if provided
    if (cleanEmail && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleanEmail)) {
      setSaveError("Please enter a valid email address (e.g. alerts@yourcompany.com).");
      return;
    }

    // Validate WhatsApp phone format if provided (at least 10 digits)
    if (cleanWa) {
      const digits = cleanWa.replace(/\D/g, "");
      if (digits.length < 10) {
        setSaveError("Please enter a valid WhatsApp phone number with at least 10 digits (e.g. +919876543210).");
        return;
      }
    }

    // When notifications are enabled, the active channel's recipient is required
    if (notifEnabled) {
      if (notifMode === "email" && !cleanEmail) {
        setSaveError("Email recipient is required when Email notification mode is enabled.");
        return;
      }
      if (notifMode === "whatsapp" && !cleanWa) {
        setSaveError("WhatsApp recipient is required when WhatsApp notification mode is enabled.");
        return;
      }
    }

    setNotifSaving(true);
    try {
      const result = await saveNotificationSettings({
        notifications_enabled: notifEnabled,
        notification_mode: notifMode,
        email_recipient: cleanEmail || null,
        whatsapp_recipient: cleanWa || null,
        notification_recipient: (notifMode === "email" ? cleanEmail : cleanWa) || null,
      });
      // Sync local state from server response
      setNotifEnabled(result.notifications_enabled);
      setNotifMode(result.notification_mode);
      setEmailRecipient(result.email_recipient ?? "");
      setWhatsappRecipient(result.whatsapp_recipient ?? "");
      setSavedMessage("Notification settings saved successfully.");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to save notification settings.";
      setSaveError(msg);
    } finally {
      setNotifSaving(false);
    }
  }

  const navItems: {
    key: SettingsSection;
    title: string;
    subtitle: string;
    icon: typeof SettingsIcon;
  }[] = [
    {
      key: "general",
      title: "General",
      subtitle: "Basic system and application settings",
      icon: SettingsIcon,
    },
    {
      key: "notifications",
      title: "Notifications",
      subtitle: "Configure notification preferences",
      icon: Bell,
    },
    {
      key: "zone_controls",
      title: "Zone & Detection Controls",
      subtitle: "Manage detection filters and ignored classes",
      icon: ShieldAlert,
    },
  ];

  return (
    <AuthGuard>
    <div className="min-h-screen bg-muted/40">
      <AppHeader />

      {/* Local-only banner */}
      <div className="mx-auto max-w-[1560px] px-6 pt-4">
        <div className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-3">
          <Info className="h-4 w-4 shrink-0 text-muted-foreground" />
          <p className="text-xs text-muted-foreground">
            Settings are stored locally in your browser and are not persisted to the server.
          </p>
        </div>
      </div>

      <main className="mx-auto grid max-w-[1560px] gap-6 p-6 lg:grid-cols-[340px_1fr]">
        <aside className="h-fit rounded-2xl border border-border bg-card p-6">
          <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Manage your system preferences and configurations
          </p>
          <div className="my-5 h-px bg-border" />
          <nav className="space-y-2">
            {navItems.map((item) => {
              const Icon = item.icon;
              const active = section === item.key;
              return (
                <button
                  key={item.key}
                  id={`tab-${item.key}`}
                  onClick={() => {
                    setSection(item.key);
                    setSavedMessage(null);
                    setSaveError(null);
                  }}
                  className={`flex w-full items-start gap-3 rounded-xl border-l-4 p-4 text-left transition-colors ${
                    active
                      ? "border-brand bg-brand-soft"
                      : "border-transparent hover:bg-accent"
                  }`}
                >
                  <Icon className={`mt-0.5 h-5 w-5 ${active ? "text-brand" : "text-muted-foreground"}`} />
                  <div>
                    <p className={`text-sm font-semibold ${active ? "text-brand" : ""}`}>
                      {item.title}
                    </p>
                    <p className="text-xs text-muted-foreground">{item.subtitle}</p>
                  </div>
                </button>
              );
            })}
          </nav>
        </aside>

        <section className="rounded-2xl border border-border bg-card p-6">
          {section === "general" && (
            <>
              <h2 className="text-2xl font-bold tracking-tight">General Settings</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Configure basic application preferences.
              </p>
              <div className="my-5 h-px bg-border" />

              <div className="mb-2 flex items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-soft text-brand">
                  <SettingsIcon className="h-4 w-4" />
                </span>
                <h3 className="text-base font-semibold">Application Preferences</h3>
              </div>

              <Row label="Facility / Site Name" description="The name of this facility or site.">
                <input
                  value={settings.facility_site_name}
                  onChange={(e) =>
                    setSettings({ ...settings, facility_site_name: e.target.value })
                  }
                  className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm font-medium outline-none focus:border-brand"
                />
              </Row>

              <Row label="Time Zone" description="Select the local time zone for this facility.">
                <Globe className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <select
                  value={settings.time_zone}
                  onChange={(e) =>
                    setSettings({ ...settings, time_zone: e.target.value })
                  }
                  className={selectClass}
                >
                  <option value="UTC">UTC</option>
                  <option value="EST">EST (Eastern Standard Time)</option>
                  <option value="CST">CST (Central Standard Time)</option>
                  <option value="PST">PST (Pacific Standard Time)</option>
                  <option value="IST">IST (Indian Standard Time)</option>
                  <option value="GMT">GMT (Greenwich Mean Time)</option>
                </select>
              </Row>

              <Row label="Date Format" description="Select the default date format.">
                <Calendar className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <select
                  value={settings.date_format}
                  onChange={(e) =>
                    setSettings({ ...settings, date_format: e.target.value as DateFormat })
                  }
                  className={selectClass}
                >
                  {Object.entries(DATE_FORMAT_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </Row>

              <Row label="Time Format" description="Select the default time format.">
                <Clock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <select
                  value={settings.time_format}
                  onChange={(e) =>
                    setSettings({ ...settings, time_format: e.target.value as TimeFormat })
                  }
                  className={selectClass}
                >
                  {Object.entries(TIME_FORMAT_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </Row>

              <Row label="Language" description="Choose your preferred language.">
                <Globe className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <select
                  value={settings.language}
                  onChange={(e) =>
                    setSettings({ ...settings, language: e.target.value as AppLanguage })
                  }
                  className={selectClass}
                >
                  {Object.entries(LANGUAGE_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </Row>



              <div className="mt-6 flex flex-wrap items-center gap-4 border-t border-border pt-6">
                <button
                  onClick={() => handleSave("General settings saved successfully.")}
                  className="inline-flex items-center gap-2 rounded-lg bg-brand px-5 py-2.5 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90"
                >
                  <Save className="h-4 w-4" />
                  Save Changes
                </button>
                <span className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                  <Info className="h-4 w-4 text-brand" />
                  Changes will be applied throughout the application.
                </span>
              </div>
            </>
          )}

          {section === "notifications" && (
            <>
              <h2 className="text-2xl font-bold tracking-tight">Notification Settings</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Choose how SafeVision AI delivers safety alerts to your organization.
                Settings are saved to your organization&apos;s profile.
              </p>
              <div className="my-5 h-px bg-border" />

              {notifLoading ? (
                <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading notification settings&hellip;
                </div>
              ) : (
                <>
                  {/* Enable/disable toggle */}
                  <div className="mb-6 flex items-center justify-between rounded-xl border border-border p-4">
                    <div>
                      <p className="text-sm font-semibold">Enable Notifications</p>
                      <p className="text-xs text-muted-foreground">
                        Send alerts to your organization when a safety event is detected.
                      </p>
                    </div>
                    <Switch
                      checked={notifEnabled}
                      onCheckedChange={setNotifEnabled}
                    />
                  </div>

                  <h3 className="text-base font-semibold">Notification Mode</h3>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Select your preferred channel to receive safety notifications.
                  </p>

                  <div className="mt-4 space-y-3">
                    {(
                      [
                        {
                          channel: "email" as const,
                          icon: Mail,
                          title: "Email",
                          line1: "Receive safety alerts through email.",
                          line2: "Detailed notifications with full event information.",
                          isDefault: true,
                          tone: "bg-brand-soft text-brand",
                        },
                        {
                          channel: "whatsapp" as const,
                          icon: MessageCircle,
                          title: "WhatsApp",
                          line1: "Receive safety alerts through WhatsApp.",
                          line2: "Concise notifications sent to your WhatsApp number.",
                          isDefault: false,
                          tone: "bg-safe-soft text-safe",
                        },
                      ]
                    ).map((mode) => {
                      const Icon = mode.icon;
                      const active = notifMode === mode.channel;
                      return (
                        <button
                          key={mode.channel}
                          onClick={() => setNotifMode(mode.channel)}
                          className={`flex w-full items-start gap-4 rounded-xl border p-4 text-left transition-colors ${
                            active ? "border-brand bg-brand-soft/40" : "border-border hover:bg-accent"
                          }`}
                        >
                          <span
                            className={`mt-1 flex h-4 w-4 items-center justify-center rounded-full border-2 ${
                              active ? "border-brand" : "border-muted-foreground/40"
                            }`}
                          >
                            {active && <span className="h-2 w-2 rounded-full bg-brand" />}
                          </span>
                          <span className={`flex h-11 w-11 items-center justify-center rounded-lg ${mode.tone}`}>
                            <Icon className="h-5 w-5" />
                          </span>
                          <span className="flex-1">
                            <span className="block text-sm font-semibold">{mode.title}</span>
                            <span className="block text-sm text-muted-foreground">{mode.line1}</span>
                            <span className="block text-sm text-muted-foreground">{mode.line2}</span>
                          </span>
                          {mode.isDefault && (
                            <span className="rounded-md bg-brand-soft px-2 py-1 text-[10px] font-bold tracking-wide text-brand">
                              DEFAULT
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>

                  <h3 className="mt-8 text-base font-semibold">Notification Channels</h3>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Configure alert recipients for both channels independently. The selected Notification Mode determines which channel dispatches automatic alerts.
                  </p>

                  <div className="mt-4 space-y-4">
                    {/* Email Recipient Card */}
                    <div className={`rounded-xl border p-4 transition-colors ${
                      notifMode === "email" ? "border-brand/60 bg-brand-soft/20" : "border-border bg-card"
                    }`}>
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-soft text-brand">
                            <Mail className="h-4 w-4" />
                          </span>
                          <span className="text-sm font-semibold">Email Recipient</span>
                        </div>
                        {notifMode === "email" ? (
                          <span className="rounded-md bg-brand-soft px-2.5 py-0.5 text-xs font-semibold text-brand tracking-wide">
                            ACTIVE DISPATCH TARGET
                          </span>
                        ) : (
                          <span className="text-xs text-muted-foreground">Standby</span>
                        )}
                      </div>
                      <input
                        id="email-recipient-input"
                        type="email"
                        value={emailRecipient}
                        onChange={(e) => setEmailRecipient(e.target.value)}
                        placeholder="user@example.com"
                        className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand"
                      />
                      <p className="mt-1.5 text-xs text-muted-foreground">
                        Enter the email address that will receive safety alerts.
                      </p>
                    </div>

                    {/* WhatsApp Recipient Card */}
                    <div className={`rounded-xl border p-4 transition-colors ${
                      notifMode === "whatsapp" ? "border-safe/60 bg-safe-soft/20" : "border-border bg-card"
                    }`}>
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-safe-soft text-safe">
                            <MessageCircle className="h-4 w-4" />
                          </span>
                          <span className="text-sm font-semibold">WhatsApp Recipient</span>
                        </div>
                        {notifMode === "whatsapp" ? (
                          <span className="rounded-md bg-safe-soft px-2.5 py-0.5 text-xs font-semibold text-safe tracking-wide">
                            ACTIVE DISPATCH TARGET
                          </span>
                        ) : (
                          <span className="text-xs text-muted-foreground">Standby</span>
                        )}
                      </div>
                      <input
                        id="whatsapp-recipient-input"
                        type="tel"
                        value={whatsappRecipient}
                        onChange={(e) => setWhatsappRecipient(e.target.value)}
                        placeholder="+919876543210"
                        className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand"
                      />
                      <p className="mt-1.5 text-xs text-muted-foreground">
                        Enter phone number in E.164 format, e.g. +919876543210.
                      </p>
                    </div>
                  </div>

                  <div className="mt-4 flex items-start gap-3 rounded-xl bg-muted/60 p-4 text-sm text-muted-foreground">
                    <Info className="mt-0.5 h-4 w-4 text-brand" />
                    Provider credentials (SMTP password, Twilio token) are configured via server
                    environment variables — never stored here. Only the recipient address is saved.
                  </div>

                  <div className="mt-6 flex flex-wrap items-center gap-3">
                    <button
                      onClick={handleSaveNotifications}
                      disabled={notifSaving}
                      className="inline-flex items-center gap-2 rounded-lg bg-brand px-5 py-2.5 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-60"
                    >
                      {notifSaving ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Save className="h-4 w-4" />
                      )}
                      {notifSaving ? "Saving…" : "Save Changes"}
                    </button>

                    {savedMessage && (
                      <div className="ml-auto inline-flex items-center gap-2 rounded-lg bg-safe-soft px-4 py-2.5 text-sm font-medium text-safe">
                        <CheckCircle2 className="h-4 w-4" />
                        {savedMessage}
                        <button onClick={() => setSavedMessage(null)} aria-label="Dismiss">
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    )}

                    {saveError && (
                      <div className="ml-auto inline-flex items-center gap-2 rounded-lg bg-destructive/10 px-4 py-2.5 text-sm font-medium text-destructive">
                        <AlertCircle className="h-4 w-4" />
                        {saveError}
                        <button onClick={() => setSaveError(null)} aria-label="Dismiss">
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    )}
                  </div>
                </>
              )}
            </>
          )}

          {section === "zone_controls" && (
            <>
              <h2 className="text-2xl font-bold tracking-tight">Zone & Detection Controls</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Manage ignored classes for video detection.
              </p>
              <div className="my-5 h-px bg-border" />

              <div className="mb-2 flex items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-soft text-brand">
                  <ShieldAlert className="h-4 w-4" />
                </span>
                <h3 className="text-base font-semibold">Ignore Class</h3>
              </div>
              <p className="mb-4 text-sm text-muted-foreground">
                Select classes to ignore. Ignored classes are hidden and do not generate events.
              </p>

              {controlsLoading ? (
                <div className="py-4 text-sm text-muted-foreground">Loading controls...</div>
              ) : (
                <div className="space-y-1 rounded-xl border border-border p-1">
                  {["PERSON", "HELMET", "SAFETY_VEST", "GOGGLES", "FIRE", "SMOKE"].map((cls) => (
                    <div key={cls} className="flex items-center justify-between rounded-lg p-3 hover:bg-accent">
                      <div className="flex flex-col">
                        <span className="text-sm font-semibold">{cls}</span>
                        <span className="text-xs text-muted-foreground">
                          {ignoredClasses.includes(cls.toLowerCase()) ? "Ignored" : "Active"}
                        </span>
                      </div>
                      <Switch
                        checked={ignoredClasses.includes(cls.toLowerCase())}
                        onCheckedChange={() => handleToggleClass(cls.toLowerCase())}
                      />
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {(section === "general" || section === "zone_controls") && savedMessage && (
            <div className="mt-4 inline-flex items-center gap-2 rounded-lg bg-safe-soft px-4 py-2.5 text-sm font-medium text-safe">
              <CheckCircle2 className="h-4 w-4" />
              {savedMessage}
              <button onClick={() => setSavedMessage(null)} aria-label="Dismiss">
                <X className="h-4 w-4" />
              </button>
            </div>
          )}
        </section>
      </main>
    </div>
    </AuthGuard>
  );
}
