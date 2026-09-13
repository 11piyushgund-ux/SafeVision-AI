import { Link } from "@tanstack/react-router";
import { motion } from "motion/react";
import {
  ArrowRight,
  ShieldCheck,
  Target,
  TrendingUp,
  ChevronRight,
  Camera,
  Map,
  SlidersHorizontal,
  BookOpen,
} from "lucide-react";
import { Reveal, RevealGroup, RevealItem } from "./Reveal";
import liveMonitoring from "@/assets/module-live-monitoring.jpg";
import safetyAlerts from "@/assets/module-safety-alerts.jpg";
import aiIntelligence from "@/assets/module-ai-intelligence.jpg";
import safetyManagement from "@/assets/module-safety-management.jpg";

const stats = [
  { icon: ShieldCheck, value: "12", label: "Active Zones" },
  { icon: Target, value: "98.7%", label: "System Confidence" },
  { icon: TrendingUp, value: "AI Monitoring", label: "Active", stacked: true },
];

function Sparkline({ tone = "alert" }: { tone?: "alert" | "brand" }) {
  return (
    <svg viewBox="0 0 44 14" className="h-3.5 w-11" fill="none" aria-hidden>
      <path
        d="M1 11 L9 7 L15 9 L23 4 L30 6 L37 2 L43 3"
        stroke={tone === "alert" ? "var(--alert)" : "var(--brand-soft)"}
        strokeWidth="1.3"
        strokeLinecap="round"
      />
    </svg>
  );
}

function CardShell({
  index,
  kicker,
  title,
  description,
  image,
  imageAlt,
  imageOverlay,
  overlay,
  side,
  accent = "brand",
  className,
  to,
}: {
  index: string;
  kicker: string;
  title: string;
  description: string;
  image?: string;
  imageAlt?: string;
  imageOverlay?: React.ReactNode;
  overlay?: React.ReactNode;
  side?: React.ReactNode;
  accent?: "brand" | "alert" | "amber" | "violet" | "teal";
  className?: string;
  to: string;
}) {
  const accentText = {
    brand: "text-brand-soft",
    alert: "text-alert",
    amber: "text-amber",
    violet: "text-violet",
    teal: "text-teal",
  }[accent];
  const chevronRing = {
    brand: "border-brand-soft/60 text-brand-soft",
    alert: "border-alert/60 text-alert",
    amber: "border-amber/60 text-amber",
    violet: "border-violet/60 text-violet",
    teal: "border-teal/60 text-teal",
  }[accent];
  const badgeBg = {
    brand: "bg-brand",
    alert: "bg-alert",
    amber: "bg-amber",
    violet: "bg-violet",
    teal: "bg-teal",
  }[accent];

  return (
    <Link
      to={to}
      className={`panel-card hover-lift group relative isolate flex min-h-[124px] overflow-hidden rounded-lg ${className ?? ""}`}
    >
      {image ? (
        <>
          <img
            src={image}
            alt={imageAlt ?? ""}
            loading="lazy"
            width={1280}
            height={720}
            className="absolute inset-0 -z-10 h-full w-full object-cover opacity-60 transition-transform duration-[1200ms] ease-out group-hover:scale-[1.04]"
          />
          <div className="absolute inset-0 -z-10 bg-gradient-to-r from-panel-2 via-panel-2/85 to-panel-2/30" />
        </>
      ) : null}
      {imageOverlay ? (
        <div className="pointer-events-none absolute inset-0 hidden sm:block" aria-hidden>
          {imageOverlay}
        </div>
      ) : null}

      <div className="relative flex w-full flex-col gap-3 p-4 pb-11 sm:flex-row sm:gap-5 sm:pb-4">
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex items-center gap-2.5">
            <span
              className={`grid h-7 w-7 shrink-0 place-items-center rounded-md text-[12px] font-bold text-primary-foreground ${badgeBg}`}
            >
              {index}
            </span>
            <span className={`micro-label truncate ${accentText}`}>{kicker}</span>
          </div>
          <h3 className="mt-2.5 text-[19px] leading-[1.15] font-bold whitespace-pre-line text-panel-foreground">
            {title}
          </h3>
          <p className="mt-1.5 max-w-[30ch] text-[11px] leading-relaxed text-panel-muted">
            {description}
          </p>
          {overlay ? <div className="mt-auto pt-3">{overlay}</div> : null}
        </div>

        {side ? <div className="w-full shrink-0 sm:w-[52%]">{side}</div> : null}

        <span
          className={`absolute right-3 bottom-3 grid h-6 w-6 place-items-center rounded-full border bg-panel-2/70 transition-transform duration-300 group-hover:translate-x-0.5 ${chevronRing}`}
        >
          <ChevronRight className="h-3.5 w-3.5" strokeWidth={2.2} />
        </span>
      </div>
    </Link>
  );
}

export function HeroModules() {
  return (
    <section className="bg-secondary/40 pt-10 pb-0 sm:pt-14">
      <div className="mx-auto max-w-[1340px] px-4 sm:px-6 lg:px-8">
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:items-start lg:gap-14">
          <Reveal>
            <h1 className="hero-title text-[clamp(2.25rem,5.2vw,4.15rem)] text-ink uppercase">
              Safety
              <br />
              <span className="text-brand">Intelligence</span>
              <br />
              For Modern
              <br />
              Manufacturing<span className="text-brand">.</span>
            </h1>
          </Reveal>

          <Reveal delay={0.12} className="lg:pt-3">
            <div className="flex flex-col gap-6 border-l border-border pl-6 lg:pl-10">
              <p className="max-w-[46ch] text-[13px] leading-relaxed text-muted-foreground">
                Monitor, detect, assess, and respond to workplace safety events through one
                intelligent command platform.
              </p>
              <RevealGroup className="grid grid-cols-1 gap-5 sm:grid-cols-3" stagger={0.1}>
                {stats.map((stat, i) => (
                  <RevealItem
                    key={stat.label}
                    className={`flex items-center gap-3 ${i > 0 ? "sm:border-l sm:border-border sm:pl-5" : ""}`}
                  >
                    <stat.icon
                      className="h-[22px] w-[22px] shrink-0 text-brand"
                      strokeWidth={1.7}
                      aria-hidden
                    />
                    <span className="min-w-0">
                      {stat.stacked ? (
                        <>
                          <span className="block text-[11px] font-bold tracking-[0.06em] text-ink uppercase">
                            {stat.value}
                          </span>
                          <span className="mt-1 block text-[10px] font-semibold tracking-[0.1em] text-online uppercase">
                            {stat.label}
                          </span>
                        </>
                      ) : (
                        <>
                          <span className="block text-[19px] leading-none font-bold text-ink">
                            {stat.value}
                          </span>
                          <span className="mt-1.5 block text-[9px] font-semibold tracking-[0.14em] text-muted-foreground uppercase">
                            {stat.label}
                          </span>
                        </>
                      )}
                    </span>
                  </RevealItem>
                ))}
              </RevealGroup>
            </div>
          </Reveal>
        </div>

        <Reveal delay={0.1} className="mt-10">
          <p className="eyebrow text-brand">Explore the Platform</p>
          <h2 className="hero-title mt-1 text-[clamp(1.35rem,2.4vw,1.75rem)] text-ink uppercase">
            Command Modules
          </h2>
        </Reveal>

        <RevealGroup
          className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-2"
          stagger={0.1}
          amount={0.1}
        >
          <RevealItem>
            <CardShell
              index="01"
              kicker="Real-Time · AI · Computer Vision"
              title="Live Monitoring"
              description="Real-time monitoring of workplace activities, PPE compliance, hazards, and restricted areas."
              image={liveMonitoring}
              imageAlt="Factory floor with robotic arm and workers under monitoring"
              accent="brand"
              to="/live-monitoring"
              imageOverlay={
                <>
                  {[
                    {
                      label: "PPE OK",
                      tone: "online",
                      left: "40%",
                      top: "40%",
                      h: "44%",
                      w: "13%",
                    },
                    {
                      label: "No Helmet",
                      tone: "alert",
                      left: "62%",
                      top: "40%",
                      h: "44%",
                      w: "13%",
                    },
                    {
                      label: "Restricted",
                      tone: "online",
                      left: "82%",
                      top: "40%",
                      h: "44%",
                      w: "13%",
                    },
                  ].map((box, i) => (
                    <motion.span
                      key={box.label}
                      initial={{ opacity: 0 }}
                      whileInView={{ opacity: 1 }}
                      viewport={{ once: true }}
                      transition={{ duration: 0.5, delay: 0.35 + i * 0.18 }}
                      className={`absolute border ${box.tone === "alert" ? "border-alert/90" : "border-online/90"}`}
                      style={{ left: box.left, top: box.top, width: box.w, height: box.h }}
                    >
                      <span
                        className={`absolute -top-[15px] left-0 px-1 text-[8px] font-bold tracking-[0.1em] whitespace-nowrap uppercase ${
                          box.tone === "alert"
                            ? "bg-alert/20 text-alert"
                            : "bg-online/20 text-online"
                        }`}
                      >
                        {box.label}
                      </span>
                    </motion.span>
                  ))}
                </>
              }
              side={
                <div className="flex h-full items-start justify-end">
                  <span className="inline-flex items-center gap-1.5">
                    <span className="h-2 w-2 animate-pulse rounded-full bg-alert" />
                    <span className="micro-label text-panel-foreground">Live</span>
                  </span>
                </div>
              }
            />
          </RevealItem>

          <RevealItem>
            <CardShell
              index="02"
              kicker="Incident · Risk · Response"
              title="Safety Alerts"
              description="View and manage real-time safety alerts and incidents that require immediate attention."
              image={safetyAlerts}
              imageAlt="Worker in red hard hat under warning lighting"
              accent="alert"
              to="/alerts"
              side={
                <div className="rounded-md border border-alert/40 bg-panel-2/80 p-2.5">
                  <span className="micro-label inline-flex items-center gap-1.5 rounded-sm bg-alert/15 px-1.5 py-0.5 text-alert">
                    High Priority Incident
                  </span>
                  <p className="mt-2 text-[12px] font-semibold text-panel-foreground">
                    Unauthorized Area Entry
                  </p>
                  <p className="text-[10px] text-panel-muted">Zone B · 10:24 AM</p>
                  <span className="micro-label mt-2 inline-block rounded-sm border border-alert/50 px-1.5 py-0.5 text-alert transition-colors hover:bg-alert/15">
                    View Incident
                  </span>
                </div>
              }
            />
          </RevealItem>

          <RevealItem>
            <CardShell
              index="03"
              kicker="Patterns · Trends · Prevention"
              title={"Recurring\nSafety Patterns"}
              description="Identify recurring safety events and trends to prevent future incidents."
              accent="violet"
              to="/patterns"
              side={
                <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
                  <div className="min-w-0 rounded-md border border-panel-border bg-panel-2/60 p-2.5">
                    <p className="micro-label text-brand-soft">Top Recurring Patterns</p>
                    <ul className="mt-2 space-y-1.5">
                      {[
                        ["PPE Violation", "27", "alert"],
                        ["Unsafe Posture", "14", "brand"],
                        ["Restricted Area Entry", "11", "amber"],
                      ].map(([label, value, tone]) => (
                        <li key={label} className="flex items-center gap-2">
                          <span
                            className={`h-1.5 w-1.5 shrink-0 rounded-full ${tone === "alert" ? "bg-alert" : tone === "amber" ? "bg-amber" : "bg-brand-soft"}`}
                          />
                          <span className="min-w-0 flex-1 truncate text-[11px] text-panel-foreground">
                            {label}
                          </span>
                          <Sparkline tone={tone === "brand" ? "brand" : "alert"} />
                          <span
                            className={`w-[22px] text-right text-[11px] font-semibold ${tone === "alert" ? "text-alert" : tone === "amber" ? "text-amber" : "text-brand-soft"}`}
                          >
                            {value}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="hidden pl-1 text-center sm:block">
                    <div className="relative mx-auto grid h-[62px] w-[62px] place-items-center">
                      <svg
                        viewBox="0 0 62 62"
                        className="absolute inset-0 h-full w-full"
                        aria-hidden
                      >
                        <circle
                          cx="31"
                          cy="31"
                          r="27"
                          fill="none"
                          stroke="var(--panel-border)"
                          strokeWidth="4"
                        />
                        <motion.circle
                          cx="31"
                          cy="31"
                          r="27"
                          fill="none"
                          stroke="var(--brand-soft)"
                          strokeWidth="4"
                          strokeLinecap="round"
                          strokeDasharray="170"
                          transform="rotate(-90 31 31)"
                          initial={{ strokeDashoffset: 170 }}
                          whileInView={{ strokeDashoffset: 124 }}
                          viewport={{ once: true }}
                          transition={{ duration: 1.1, delay: 0.3, ease: [0.22, 1, 0.36, 1] }}
                        />
                      </svg>
                      <span className="relative text-[15px] leading-none font-bold text-panel-foreground">
                        27%
                      </span>
                    </div>
                    <p className="mt-2 text-[9px] leading-tight text-panel-muted">
                      Increase vs
                      <br />
                      last month
                    </p>
                  </div>
                </div>
              }
            />
          </RevealItem>

          <RevealItem>
            <CardShell
              index="04"
              kicker="Analytics · Patterns · Recommendations"
              title={"AI Safety\nIntelligence"}
              description="AI-powered insights, risk assessment, and recommendations for a safer workplace."
              image={aiIntelligence}
              imageAlt="Abstract blue particle cluster"
              accent="brand"
              to="/ai-safety-insights"
              side={
                <div className="rounded-md border border-brand-soft/25 bg-panel-2/70 p-2.5">
                  <p className="micro-label text-brand-soft">Top Risk Factors</p>
                  <ul className="mt-2 space-y-1.5">
                    {[
                      ["No Helmet", "32%"],
                      ["Unsafe Posture", "24%"],
                      ["Machine Proximity", "19%"],
                    ].map(([label, value]) => (
                      <li key={label} className="flex items-center gap-2">
                        <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-brand-soft" />
                        <span className="min-w-0 flex-1 truncate text-[11px] text-panel-foreground">
                          {label}
                        </span>
                        <span className="text-[11px] font-semibold text-brand-soft">{value}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              }
            />
          </RevealItem>

          <RevealItem>
            <CardShell
              index="05"
              kicker="Timeline · Events · Context"
              title={"Event\nHistory"}
              description="Browse and analyze historical safety events and incidents for investigation and reporting."
              accent="teal"
              to="/event-history"
              side={
                <ul className="relative space-y-2.5">
                  {[
                    ["10:24 AM", "Unauthorized Area Entry", "Zone B", liveMonitoring],
                    ["10:18 AM", "Unsafe Posture Detected", "Zone A", safetyAlerts],
                    ["10:12 AM", "Helmet Not Detected", "Zone C", safetyManagement],
                  ].map(([time, event, zone, thumb]) => (
                    <li key={time} className="flex items-center gap-3">
                      <span className="h-2 w-2 shrink-0 rounded-full bg-teal ring-2 ring-teal/25" />
                      <span className="w-[58px] shrink-0 text-[10px] font-semibold text-panel-foreground">
                        {time}
                      </span>
                      <span className="min-w-0 flex-1 border-l border-panel-border pl-3">
                        <span className="block truncate text-[11px] text-panel-foreground">
                          {event}
                        </span>
                        <span className="block text-[10px] text-panel-muted">{zone}</span>
                      </span>
                      <img
                        src={thumb}
                        alt=""
                        loading="lazy"
                        className="hidden h-8 w-12 shrink-0 rounded-sm border border-panel-border object-cover opacity-80 sm:block"
                      />
                    </li>
                  ))}
                </ul>
              }
            />
          </RevealItem>

          <RevealItem>
            <CardShell
              index="06"
              kicker="Configure · Manage · Control"
              title={"Safety\nManagement"}
              description="Manage cameras, zones, safety rules, and system settings to maintain a secure environment."
              image={safetyManagement}
              imageAlt="Security control room with monitor wall"
              accent="amber"
              to="/documents"
              side={
                <ul className="space-y-1.5">
                  {[
                    [Camera, "Camera Management"],
                    [Map, "Zone & Area Configuration"],
                    [SlidersHorizontal, "Safety Rules & Settings"],
                    [BookOpen, "SOP & Knowledge Management"],
                  ].map(([Icon, label]) => {
                    const Ic = Icon as typeof Camera;
                    return (
                      <li key={label as string} className="flex items-center gap-2">
                        <Ic className="h-3 w-3 shrink-0 text-brand-soft" strokeWidth={1.9} />
                        <span className="min-w-0 truncate text-[10.5px] text-panel-foreground">
                          {label as string}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              }
            />
          </RevealItem>
        </RevealGroup>
      </div>

      <motion.div
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true }}
        transition={{ duration: 0.6 }}
        className="mt-8 border-t border-border bg-card"
      >
        <div className="mx-auto flex max-w-[1340px] flex-col gap-3 px-4 py-4 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <span className="text-[13px] font-bold text-ink">
              SafeVision <span className="text-brand">AI</span>
            </span>
            <span className="hidden h-4 w-px bg-border sm:block" />
            <span className="min-w-0 text-[10px] leading-tight text-muted-foreground">
              Building safer industrial environments through intelligent vision.
            </span>
          </div>
          <p className="text-[10px] text-muted-foreground">
            © 2026 SafeVision AI. All rights reserved.
          </p>
          <nav className="flex flex-wrap items-center gap-4 text-[10px] text-muted-foreground">
            {["Help Center", "Documentation", "Privacy Policy"].map((item) => (
              <a
                key={item}
                href="#"
                className="transition-colors hover:text-brand"
                onClick={(event) => event.preventDefault()}
              >
                {item}
              </a>
            ))}
          </nav>
        </div>
      </motion.div>
    </section>
  );
}

export { ArrowRight };
