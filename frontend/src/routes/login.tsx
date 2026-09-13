import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { ArrowRight, Brain, Eye, EyeOff, Loader2, Lock, Mail, ScanEye, ShieldCheck, Activity } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth-context";

const title = "Sign in — SafeVision AI Safety Command Center";
const description =
  "Sign in to your SafeVision AI Safety Command Center to monitor, understand, and respond to safety events in real time.";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title },
      { name: "description", content: description },
      { property: "og:title", content: title },
      { property: "og:description", content: description },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: LoginPage,
});

const zones = [
  { id: "A", state: "Monitoring", accent: "text-brand-soft", ring: "ring-brand/40", pos: "left-[8%] top-[26%]" },
  { id: "B", state: "Active", accent: "text-brand-soft", ring: "ring-brand/50", pos: "left-[46%] top-[20%]" },
  { id: "C", state: "Secure", accent: "text-teal", ring: "ring-teal/40", pos: "right-[6%] top-[35%]" },
  { id: "D", state: "Monitoring", accent: "text-violet", ring: "ring-violet/40", pos: "left-[42%] bottom-[26%]" },
];

const stats = [
  { icon: ShieldCheck, value: "12", unit: "", label: "Active", sub: "Safety Zones", tone: "text-online" },
  { icon: Brain, value: "98.7", unit: "%", label: "System", sub: "Confidence", tone: "text-brand-soft" },
  { icon: Activity, value: "2.4K", unit: "", label: "Events", sub: "Monitored Today", tone: "text-violet" },
];

function LoginPage() {
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [emailError, setEmailError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const { login, isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();

  // Redirect if already authenticated
  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      navigate({ to: "/alerts" });
    }
  }, [isLoading, isAuthenticated, navigate]);

  const validateForm = (cleanEmail: string) => {
    let valid = true;

    if (!cleanEmail) {
      setEmailError("Work email is required.");
      valid = false;
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleanEmail)) {
      setEmailError("Please enter a valid work email address.");
      valid = false;
    } else {
      setEmailError(null);
    }

    if (!password) {
      setPasswordError("Password is required.");
      valid = false;
    } else {
      setPasswordError(null);
    }

    return valid;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const cleanEmail = email.trim();
    if (!validateForm(cleanEmail)) {
      return;
    }

    setIsSubmitting(true);
    try {
      await login(cleanEmail, password, remember);
      toast.success("Welcome back!");
      navigate({ to: "/alerts" });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Login failed";
      setError(message);
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleForgotPassword = (e: React.MouseEvent) => {
    e.preventDefault();
    toast.info("Password reset is managed by your organization administrator. Please contact your system admin (admin@safevision.local).", {
      duration: 6000,
    });
  };

  const handleAlternativeSignIn = (provider: string) => {
    toast.info(`Enterprise Single Sign-On (${provider} SSO) is available on the Enterprise plan. Please sign in with your work credentials.`, {
      duration: 5000,
    });
  };

  return (
    <div className="min-h-screen bg-canvas lg:grid lg:grid-cols-[minmax(0,0.46fr)_minmax(0,0.54fr)]">
      {/* Left brand panel */}
      <section className="relative isolate flex flex-col overflow-hidden bg-panel-2 px-7 py-9 text-panel-foreground sm:px-10 lg:px-12 lg:py-11">
        <div
          className="pointer-events-none absolute inset-0 -z-10 opacity-90"
          style={{
            background:
              "radial-gradient(120% 80% at 50% 30%, oklch(0.24 0.07 265) 0%, oklch(0.145 0.028 262) 65%)",
          }}
        />

        <Link to="/" className="flex items-center gap-3">
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-brand/15 text-brand-soft ring-1 ring-brand/30">
            <ScanEye className="h-6 w-6" strokeWidth={1.9} />
          </span>
          <span className="leading-none">
            <span className="block text-[22px] font-bold tracking-tight text-panel-foreground">
              SafeVision AI
            </span>
            <span className="mt-1.5 block text-[10px] font-semibold tracking-[0.18em] text-panel-muted uppercase">
              Safety Intelligence Platform
            </span>
          </span>
        </Link>

        {/* Illustration */}
        <motion.div
          initial={{ opacity: 0, scale: 0.97 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
          className="relative mx-auto mt-10 w-full max-w-[520px]"
        >
          <img
            src="/login-factory-transparent.png"
            alt="Isometric illustration of a monitored smart factory with connected safety zones"
            className="w-full select-none"
            loading="eager"
          />
          {zones.map((z, i) => (
            <motion.span
              key={z.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.5 + i * 0.15, ease: [0.22, 1, 0.36, 1] }}
              className={`absolute ${z.pos} rounded-md bg-panel-2/85 px-2.5 py-1.5 ring-1 ${z.ring} backdrop-blur-sm`}
            >
              <span className="block text-[10px] font-bold tracking-[0.12em] text-panel-foreground uppercase">
                Zone {z.id}
              </span>
              <span className={`block text-[10px] font-medium ${z.accent}`}>{z.state}</span>
            </motion.span>
          ))}
        </motion.div>

        <div className="mt-auto pt-10">
          <h2 className="hero-title text-[38px] text-panel-foreground sm:text-[44px]">
            Securing the
            <br />
            <span className="text-brand-soft">Industrial </span>
            <span className="text-violet">Frontier.</span>
          </h2>
          <p className="mt-4 max-w-[420px] text-[15px] leading-relaxed text-panel-muted">
            AI-powered real-time safety intelligence for modern manufacturing environments.
          </p>

          <div className="mt-8 border-t border-panel-border pt-6">
            <span className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-online" />
              <span className="text-[13px] font-bold tracking-[0.1em] text-panel-foreground uppercase">
                AI Monitoring Active
              </span>
            </span>

            <div className="mt-6 grid grid-cols-3 gap-4">
              {stats.map((s) => (
                <div key={s.sub}>
                  <span className="grid h-9 w-9 place-items-center rounded-lg bg-panel/80 ring-1 ring-panel-border">
                    <s.icon className={`h-4 w-4 ${s.tone}`} strokeWidth={1.9} />
                  </span>
                  <p className="mt-3 text-[26px] leading-none font-bold tracking-tight text-panel-foreground">
                    {s.value}
                    {s.unit && <span className="text-[15px] font-semibold">{s.unit}</span>}
                  </p>
                  <p className={`mt-2 text-[11px] font-bold tracking-[0.1em] uppercase ${s.tone}`}>
                    {s.label}
                  </p>
                  <p className="text-[11px] font-semibold tracking-[0.1em] text-panel-muted uppercase">
                    {s.sub}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <p className="mt-8 text-[11px] text-panel-muted">
            © 2025 SafeVision AI &nbsp;·&nbsp; Industrial Safety Intelligence
          </p>
        </div>
      </section>

      {/* Right form panel */}
      <section className="relative flex items-center justify-center overflow-hidden px-6 py-14 sm:px-10 lg:px-16">
        <div
          className="pointer-events-none absolute -top-40 -right-40 h-[520px] w-[520px] rounded-full opacity-60"
          style={{ background: "radial-gradient(circle, var(--brand-tint) 0%, transparent 70%)" }}
        />
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          className="relative w-full max-w-[560px]"
        >
          <p className="eyebrow text-brand">Welcome back</p>
          <h1 className="hero-title mt-4 text-[38px] text-ink sm:text-[44px]">
            Sign in to your
            <br />
            <span className="text-brand">Safety </span>Command Center
          </h1>
          <p className="mt-4 text-[15px] text-muted-foreground">
            Monitor, understand, and respond to safety events in real time.
          </p>

          <form className="mt-9 space-y-5" onSubmit={handleSubmit}>
            <div>
              <label htmlFor="email" className="block text-[14px] font-semibold text-ink">
                Work Email
              </label>
              <div className="relative mt-2">
                <Mail
                  className="pointer-events-none absolute top-1/2 left-4 h-[18px] w-[18px] -translate-y-1/2 text-muted-foreground"
                  strokeWidth={1.8}
                />
                <input
                  id="email"
                  type="email"
                  autoFocus
                  autoComplete="email"
                  placeholder="you@company.com"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (emailError) setEmailError(null);
                    if (error) setError(null);
                  }}
                  disabled={isSubmitting}
                  aria-invalid={!!emailError}
                  className={`h-14 w-full rounded-xl border bg-card pl-12 pr-4 text-[15px] text-ink shadow-card outline-none transition-colors placeholder:text-muted-foreground focus:ring-2 disabled:opacity-50 ${
                    emailError
                      ? "border-destructive focus:border-destructive focus:ring-destructive/20"
                      : "border-border focus:border-brand focus:ring-brand/20"
                  }`}
                />
              </div>
              {emailError && (
                <p className="mt-1.5 text-[13px] font-medium text-destructive">{emailError}</p>
              )}
            </div>

            <div>
              <label htmlFor="password" className="block text-[14px] font-semibold text-ink">
                Password
              </label>
              <div className="relative mt-2">
                <Lock
                  className="pointer-events-none absolute top-1/2 left-4 h-[18px] w-[18px] -translate-y-1/2 text-muted-foreground"
                  strokeWidth={1.8}
                />
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (passwordError) setPasswordError(null);
                    if (error) setError(null);
                  }}
                  disabled={isSubmitting}
                  aria-invalid={!!passwordError}
                  className={`h-14 w-full rounded-xl border bg-card pr-12 pl-12 text-[15px] text-ink shadow-card outline-none transition-colors placeholder:text-muted-foreground focus:ring-2 disabled:opacity-50 ${
                    passwordError
                      ? "border-destructive focus:border-destructive focus:ring-destructive/20"
                      : "border-border focus:border-brand focus:ring-brand/20"
                  }`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  title={showPassword ? "Hide password" : "Show password"}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  className="absolute top-1/2 right-3 grid h-9 w-9 -translate-y-1/2 place-items-center rounded-md text-muted-foreground transition-colors hover:text-ink"
                >
                  {showPassword ? (
                    <Eye className="h-[18px] w-[18px]" strokeWidth={1.8} />
                  ) : (
                    <EyeOff className="h-[18px] w-[18px]" strokeWidth={1.8} />
                  )}
                </button>
              </div>
              {passwordError && (
                <p className="mt-1.5 text-[13px] font-medium text-destructive">{passwordError}</p>
              )}
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3">
              <label
                onClick={() => setRemember((v) => !v)}
                className="flex cursor-pointer select-none items-center gap-2.5 text-[14px] text-ink"
              >
                <button
                  type="button"
                  role="checkbox"
                  id="remember-device-checkbox"
                  aria-checked={remember}
                  onClick={(e) => {
                    e.stopPropagation();
                    setRemember((v) => !v);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === " " || e.key === "Enter") {
                      e.preventDefault();
                      setRemember((v) => !v);
                    }
                  }}
                  className={`grid h-[18px] w-[18px] place-items-center rounded-[5px] border transition-colors ${
                    remember ? "border-brand bg-brand" : "border-input bg-card"
                  }`}
                >
                  {remember && (
                    <svg viewBox="0 0 12 12" className="h-3 w-3 text-primary-foreground" fill="none">
                      <path
                        d="M2.5 6.2l2.2 2.2 4.8-4.8"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  )}
                </button>
                Remember this device
              </label>
              <button
                type="button"
                id="btn-forgot-password"
                onClick={handleForgotPassword}
                className="text-[14px] font-medium text-brand hover:underline cursor-pointer"
              >
                Forgot password?
              </button>
            </div>

            {error && (
              <div className="rounded-xl border border-destructive/20 bg-destructive/10 p-3 text-[13px] font-medium text-destructive">
                {error}
              </div>
            )}

            <button
              type="submit"
              id="btn-login-submit"
              disabled={isSubmitting}
              className="group flex h-14 w-full items-center justify-center gap-3 rounded-xl bg-brand text-[14px] font-bold tracking-[0.08em] text-primary-foreground uppercase shadow-lift transition-all duration-300 hover:brightness-110 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-[18px] w-[18px] animate-spin" strokeWidth={2} />
                  Signing in…
                </>
              ) : (
                <>
                  Enter Command Center
                  <ArrowRight
                    className="h-[18px] w-[18px] transition-transform duration-300 group-hover:translate-x-1"
                    strokeWidth={2}
                  />
                </>
              )}
            </button>
          </form>

          <div className="mt-9 flex items-center gap-4">
            <span className="h-px flex-1 bg-border" />
            <span className="micro-label text-muted-foreground">Or continue with</span>
            <span className="h-px flex-1 bg-border" />
          </div>

          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            <button
              type="button"
              id="btn-sso-google"
              onClick={() => handleAlternativeSignIn("Google")}
              className="flex h-14 items-center justify-center gap-3 rounded-xl border border-border bg-card text-[15px] font-medium text-ink shadow-card transition-colors hover:bg-secondary cursor-pointer"
            >
              <GoogleMark />
              Continue with Google
            </button>
            <button
              type="button"
              id="btn-sso-microsoft"
              onClick={() => handleAlternativeSignIn("Microsoft")}
              className="flex h-14 items-center justify-center gap-3 rounded-xl border border-border bg-card text-[15px] font-medium text-ink shadow-card transition-colors hover:bg-secondary cursor-pointer"
            >
              <MicrosoftMark />
              Continue with Microsoft
            </button>
          </div>

          <div className="mt-10 flex items-center justify-center gap-3">
            <span className="grid h-9 w-9 place-items-center rounded-full bg-brand-tint text-brand">
              <ShieldCheck className="h-[18px] w-[18px]" strokeWidth={1.9} />
            </span>
            <span className="text-[14px] text-muted-foreground">
              Protected access to industrial safety intelligence.
            </span>
          </div>
        </motion.div>
      </section>
    </div>
  );
}

function GoogleMark() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.4h6.4a5.5 5.5 0 0 1-2.4 3.6v3h3.9c2.3-2.1 3.6-5.2 3.6-8.7z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.2 0 5.9-1.1 7.9-2.9l-3.9-3a7.2 7.2 0 0 1-10.7-3.8H1.3v3.1A12 12 0 0 0 12 24z"
      />
      <path fill="#FBBC05" d="M5.3 14.3a7.2 7.2 0 0 1 0-4.6V6.6H1.3a12 12 0 0 0 0 10.8l4-3.1z" />
      <path
        fill="#EA4335"
        d="M12 4.8c1.8 0 3.4.6 4.6 1.8l3.5-3.5A12 12 0 0 0 1.3 6.6l4 3.1A7.2 7.2 0 0 1 12 4.8z"
      />
    </svg>
  );
}

function MicrosoftMark() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden="true">
      <path fill="#F25022" d="M2 2h9.4v9.4H2z" />
      <path fill="#7FBA00" d="M12.6 2H22v9.4h-9.4z" />
      <path fill="#00A4EF" d="M2 12.6h9.4V22H2z" />
      <path fill="#FFB900" d="M12.6 12.6H22V22h-9.4z" />
    </svg>
  );
}
