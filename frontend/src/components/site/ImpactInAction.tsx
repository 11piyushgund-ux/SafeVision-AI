import { motion, useReducedMotion } from "motion/react";
import {
  ScanSearch,
  ShieldCheck,
  BookOpen,
  BellRing,
  AlertTriangle,
  MapPin,
  BarChart3,
  FileText,
  Timer,
  Users,
  Shield,
  TrendingUp,
  Target,
} from "lucide-react";
import { Reveal, RevealGroup, RevealItem } from "./Reveal";
import worker from "@/assets/event-worker.jpg";

type Point = {
  n: string;
  icon: typeof ScanSearch;
  title: string;
  copy: string;
  subIcon: typeof ScanSearch;
  subCopy: string;
  align: "left" | "right";
};

const points: Point[] = [
  {
    n: "01",
    icon: ScanSearch,
    title: "Detection",
    copy: "AI detects a safety violation in real time.",
    subIcon: BellRing,
    subCopy: "Instant alert created with event details.",
    align: "left",
  },
  {
    n: "02",
    icon: ShieldCheck,
    title: "Understanding the Risk",
    copy: "The event is analyzed to evaluate its severity and context.",
    subIcon: BarChart3,
    subCopy: "Risk level, location, time, and activity are considered.",
    align: "right",
  },
  {
    n: "03",
    icon: BookOpen,
    title: "Intelligence & Context",
    copy: "SafeVision AI connects the event with relevant safety knowledge.",
    subIcon: FileText,
    subCopy: "SOPs identified and recommended actions are suggested.",
    align: "left",
  },
  {
    n: "04",
    icon: BellRing,
    title: "Action & Continuous Improvement",
    copy: "Alerts are sent, the event is recorded, and insights are generated.",
    subIcon: Timer,
    subCopy: "Every event drives learning and helps prevent future incidents.",
    align: "right",
  },
];

const outcomes = [
  { icon: Users, title: "Protect People", copy: "Reduce risks and prevent injuries." },
  { icon: Shield, title: "Ensure Compliance", copy: "Maintain standards and avoid penalties." },
  { icon: TrendingUp, title: "Drive Insights", copy: "Turn data into action and improvement." },
  {
    icon: Target,
    title: "Build a Safer Culture",
    copy: "Empower teams to make safety a priority.",
  },
];

function PointBlock({ point, delay }: { point: Point; delay: number }) {
  const alignClass = point.align === "right" ? "lg:items-start" : "lg:items-start";

  return (
    <Reveal delay={delay} className={`flex flex-col ${alignClass}`}>
      <div className="flex items-center gap-2.5">
        <span className="grid h-7 w-7 place-items-center rounded-full bg-brand text-[11px] font-bold text-primary-foreground">
          {point.n}
        </span>
        <span className="grid h-7 w-7 place-items-center rounded-full border border-brand/30 bg-brand/10 text-brand">
          <point.icon className="h-3.5 w-3.5" strokeWidth={1.9} aria-hidden />
        </span>
      </div>
      <h3 className="mt-3 text-[11px] font-bold tracking-[0.14em] text-ink uppercase">
        {point.title}
      </h3>
      <p className="mt-2 max-w-[34ch] text-[11.5px] leading-relaxed text-muted-foreground">
        {point.copy}
      </p>
      <div className="mt-4 flex max-w-[34ch] gap-2.5 border-t border-border pt-3">
        <span className="grid h-6 w-6 shrink-0 place-items-center rounded border border-border bg-card text-brand">
          <point.subIcon className="h-3 w-3" strokeWidth={1.9} aria-hidden />
        </span>
        <p className="text-[11px] leading-relaxed text-muted-foreground">{point.subCopy}</p>
      </div>
    </Reveal>
  );
}

export function ImpactInAction() {
  const reduced = useReducedMotion();

  return (
    <section className="bg-card py-16 sm:py-24">
      <div className="mx-auto max-w-[1340px] px-4 sm:px-6 lg:px-8">
        <Reveal className="text-center">
          <div className="flex items-center justify-center gap-3">
            <span className="h-px w-8 bg-brand/40" />
            <p className="eyebrow text-brand">Real-Time Impact in Action</p>
            <span className="h-px w-8 bg-brand/40" />
          </div>
          <h2 className="display-title mx-auto mt-5 max-w-[26ch] text-[clamp(2rem,4.4vw,3.4rem)] text-ink">
            A Safety Event,
            <br />
            <span className="text-brand">Before</span> It Becomes an Incident.
          </h2>
          <p className="mx-auto mt-6 max-w-[64ch] text-[13px] leading-relaxed text-muted-foreground">
            SafeVision AI doesn't just detect — it understands the context, evaluates the risk,
            recommends the right action, and ensures continuous improvement.
          </p>
        </Reveal>

        <div className="mt-14 grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)_minmax(0,1fr)] lg:gap-8">
          <div className="flex flex-col gap-12">
            <PointBlock point={points[0]!} delay={0} />
            <PointBlock point={points[2]!} delay={0.5} />
          </div>

          <Reveal
            delay={0.15}
            className="relative self-start overflow-hidden rounded-md border border-border shadow-lift"
          >
            <img
              src={worker}
              alt="Warehouse worker without a helmet walking through a storage aisle"
              loading="lazy"
              width={1280}
              height={864}
              className="block h-full w-full object-cover"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-panel-2/85 via-transparent to-panel-2/20" />

            <motion.div
              initial={reduced ? { opacity: 0 } : { opacity: 0, scale: 1.08 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true, amount: 0.4 }}
              transition={{ duration: 0.8, delay: 0.4, ease: [0.22, 1, 0.36, 1] }}
              className="absolute top-[16%] left-1/2 h-[34%] w-[26%] -translate-x-1/2 rounded-sm border-2 border-alert/90"
              aria-hidden
            />
            <motion.span
              initial={{ opacity: 0, y: -6 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.4 }}
              transition={{ duration: 0.5, delay: 0.7 }}
              className="absolute top-[13%] right-[14%] grid h-7 w-7 place-items-center rounded-sm bg-alert text-primary-foreground shadow-panel"
              aria-hidden
            >
              <AlertTriangle className="h-4 w-4" strokeWidth={2.2} />
            </motion.span>

            <motion.div
              initial={{ opacity: 0, y: 14 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.4 }}
              transition={{ duration: 0.6, delay: 0.9, ease: [0.22, 1, 0.36, 1] }}
              className="absolute inset-x-3 bottom-3 grid grid-cols-1 gap-2 rounded-sm border border-panel-border bg-panel-2/90 p-2.5 backdrop-blur-sm sm:grid-cols-3"
            >
              <div className="flex min-w-0 items-center gap-2">
                <AlertTriangle className="h-4 w-4 shrink-0 text-alert" strokeWidth={2} />
                <span className="min-w-0">
                  <span className="micro-label block text-alert">PPE Violation</span>
                  <span className="mt-0.5 block truncate text-[11px] text-panel-foreground">
                    Helmet not detected
                  </span>
                </span>
              </div>
              <div className="flex min-w-0 items-center gap-2 sm:border-l sm:border-panel-border sm:pl-3">
                <MapPin className="h-4 w-4 shrink-0 text-panel-muted" strokeWidth={2} />
                <span className="min-w-0">
                  <span className="micro-label block text-panel-muted">Location</span>
                  <span className="mt-0.5 block truncate text-[11px] text-panel-foreground">
                    Assembly Zone B
                  </span>
                </span>
              </div>
              <div className="flex min-w-0 items-center gap-2 sm:border-l sm:border-panel-border sm:pl-3">
                <ShieldCheck className="h-4 w-4 shrink-0 text-panel-muted" strokeWidth={2} />
                <span className="min-w-0 flex-1">
                  <span className="micro-label block text-panel-muted">Risk Level</span>
                  <span className="mt-0.5 flex items-center gap-2">
                    <span className="text-[11px] font-semibold text-alert">High</span>
                    <span className="flex items-end gap-[2px]" aria-hidden>
                      {[5, 8, 11, 14].map((h) => (
                        <span
                          key={h}
                          style={{ height: `${h}px` }}
                          className="w-[3px] rounded-sm bg-alert/80"
                        />
                      ))}
                    </span>
                  </span>
                </span>
              </div>
            </motion.div>
          </Reveal>

          <div className="flex flex-col gap-12">
            <PointBlock point={points[1]!} delay={0.25} />
            <PointBlock point={points[3]!} delay={0.75} />
          </div>
        </div>

        <Reveal delay={0.1} className="mt-14">
          <div className="grid gap-6 rounded-md border border-border bg-secondary/40 p-5 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,2.1fr)] lg:items-center lg:gap-8">
            <div className="flex min-w-0 items-center gap-3">
              <span className="grid h-11 w-11 shrink-0 place-items-center rounded-md bg-brand text-primary-foreground shadow-card">
                <Shield className="h-5 w-5" strokeWidth={1.9} aria-hidden />
              </span>
              <p className="hero-title text-[15px] leading-snug text-ink uppercase">
                From a Single Event
                <br />
                <span className="text-brand">To a Smarter</span>
                <br />
                <span className="text-brand">Safety System.</span>
              </p>
            </div>
            <RevealGroup className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4" stagger={0.1}>
              {outcomes.map((item) => (
                <RevealItem
                  key={item.title}
                  className="group flex min-w-0 gap-2.5 sm:border-l sm:border-border sm:pl-4"
                >
                  <item.icon
                    className="mt-0.5 h-4 w-4 shrink-0 text-brand transition-transform duration-300 group-hover:scale-110"
                    strokeWidth={1.9}
                    aria-hidden
                  />
                  <span className="min-w-0">
                    <span className="block text-[11.5px] font-bold text-ink">{item.title}</span>
                    <span className="mt-1 block text-[11px] leading-relaxed text-muted-foreground">
                      {item.copy}
                    </span>
                  </span>
                </RevealItem>
              ))}
            </RevealGroup>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
