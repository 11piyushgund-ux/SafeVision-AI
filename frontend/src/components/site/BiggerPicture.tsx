import { motion, useReducedMotion } from "motion/react";
import {
  Database,
  MapPin,
  AlertTriangle,
  Users,
  BarChart3,
  FileText,
  ShieldCheck,
  BellRing,
  Eye,
  Network,
  Zap,
} from "lucide-react";
import { Reveal, RevealGroup, RevealItem } from "./Reveal";

type Node = {
  key: string;
  icon: typeof Database;
  title: string;
  copy: string;
  /** position on the ring, in percent of the square container */
  x: number;
  y: number;
  labelSide: "left" | "right" | "center";
};

const nodes: Node[] = [
  {
    key: "recorded",
    icon: Database,
    title: "Event Recorded",
    copy: "Captured and stored securely.",
    x: 50,
    y: 4,
    labelSide: "right",
  },
  {
    key: "context",
    icon: MapPin,
    title: "Context",
    copy: "Location, zone, time and conditions.",
    x: 89,
    y: 27,
    labelSide: "right",
  },
  {
    key: "risk",
    icon: AlertTriangle,
    title: "Risk Analysis",
    copy: "Assessed severity and potential impact.",
    x: 89,
    y: 73,
    labelSide: "right",
  },
  {
    key: "actionable",
    icon: Users,
    title: "Actionable Intelligence",
    copy: "Enabling proactive decisions and preventive actions.",
    x: 50,
    y: 96,
    labelSide: "right",
  },
  {
    key: "patterns",
    icon: BarChart3,
    title: "Safety Patterns",
    copy: "Identifying trends and recurring risks.",
    x: 11,
    y: 73,
    labelSide: "left",
  },
  {
    key: "data",
    icon: FileText,
    title: "Event Data",
    copy: "Structured and organized information.",
    x: 11,
    y: 27,
    labelSide: "left",
  },
];

const principles = [
  { icon: Eye, label: "See." },
  { icon: Network, label: "Understand." },
  { icon: Zap, label: "Act." },
  { icon: BarChart3, label: "Improve." },
];

export function BiggerPicture() {
  const reduced = useReducedMotion();

  return (
    <section className="bg-canvas py-16 sm:py-24">
      <div className="mx-auto max-w-[1340px] px-4 sm:px-6 lg:px-8">
        <Reveal className="text-center">
          <p className="eyebrow text-brand">The Bigger Picture</p>
          <span className="mx-auto mt-4 block h-px w-16 bg-brand/40" />
          <h2 className="display-title mx-auto mt-5 max-w-[26ch] text-[clamp(1.9rem,4.4vw,3.3rem)] text-ink uppercase">
            From a Single Event,
            <br />
            to a <span className="text-brand">Smarter Safety System.</span>
          </h2>
          <p className="mx-auto mt-6 max-w-[66ch] text-[13px] leading-relaxed text-muted-foreground">
            Every event contributes to a clearer understanding of workplace safety, turning
            real-time observations into intelligence that supports better decisions over time.
          </p>
        </Reveal>

        {/* Desktop ecosystem */}
        <div className="mt-16 hidden lg:block">
          <div className="relative mx-auto aspect-square w-full max-w-[620px]">
            <svg
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
              className="absolute inset-0 h-full w-full"
              aria-hidden
            >
              <motion.circle
                cx="50"
                cy="50"
                r="42"
                fill="none"
                stroke="var(--border)"
                strokeWidth="0.25"
                strokeDasharray="1.6 1.6"
                initial={{ opacity: 0, scale: 0.9 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true, amount: 0.3 }}
                transition={{ duration: 1, delay: 0.3 }}
                style={{ transformOrigin: "50% 50%" }}
              />
              {nodes.map((node, i) => (
                <motion.line
                  key={node.key}
                  x1="50"
                  y1="50"
                  x2={node.x}
                  y2={node.y}
                  stroke="var(--brand)"
                  strokeOpacity="0.35"
                  strokeWidth="0.25"
                  initial={reduced ? { opacity: 0 } : { pathLength: 0, opacity: 0 }}
                  whileInView={{ pathLength: 1, opacity: 1 }}
                  viewport={{ once: true, amount: 0.3 }}
                  transition={{ duration: 0.8, delay: 0.35 + i * 0.12 }}
                />
              ))}
            </svg>

            {/* Center node */}
            <motion.div
              initial={reduced ? { opacity: 0 } : { opacity: 0, scale: 0.8 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true, amount: 0.3 }}
              transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
              className="absolute top-1/2 left-1/2 flex -translate-x-1/2 -translate-y-1/2 flex-col items-center"
            >
              <span className="relative grid h-[74px] w-[74px] place-items-center rounded-full bg-brand text-primary-foreground shadow-lift">
                <span className="absolute inset-0 rounded-full ring-8 ring-brand/10" />
                <BellRing className="h-7 w-7" strokeWidth={1.7} aria-hidden />
              </span>
              <span className="mt-3 text-[10px] font-bold tracking-[0.16em] text-ink uppercase">
                One Event
              </span>
            </motion.div>

            {nodes.map((node, i) => (
              <motion.div
                key={node.key}
                initial={reduced ? { opacity: 0 } : { opacity: 0, scale: 0.85 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true, amount: 0.3 }}
                transition={{ duration: 0.6, delay: 0.5 + i * 0.12, ease: [0.22, 1, 0.36, 1] }}
                className="absolute flex -translate-x-1/2 -translate-y-1/2 items-center gap-3"
                style={{
                  left: `${node.x}%`,
                  top: `${node.y}%`,
                  flexDirection: node.labelSide === "left" ? "row-reverse" : "row",
                }}
              >
                <span className="group grid h-12 w-12 shrink-0 place-items-center rounded-full border border-border bg-card text-brand shadow-card transition-transform duration-300 hover:-translate-y-0.5">
                  <node.icon className="h-5 w-5" strokeWidth={1.7} aria-hidden />
                </span>
                <span
                  className={`w-[132px] ${node.labelSide === "left" ? "text-right" : "text-left"}`}
                >
                  <span className="block text-[10px] font-bold tracking-[0.14em] text-ink uppercase">
                    {node.title}
                  </span>
                  <span className="mt-1 block text-[10.5px] leading-relaxed text-muted-foreground">
                    {node.copy}
                  </span>
                </span>
              </motion.div>
            ))}
          </div>

          <Reveal delay={0.2} className="mx-auto mt-6 flex max-w-[620px] items-center gap-3">
            <span className="grid h-12 w-12 shrink-0 place-items-center rounded-full border border-brand/25 bg-brand/10 text-brand">
              <ShieldCheck className="h-5 w-5" strokeWidth={1.7} aria-hidden />
            </span>
            <span>
              <span className="block text-[10px] font-bold tracking-[0.14em] text-ink uppercase">
                Smarter Safety System
              </span>
              <span className="mt-1 block text-[10.5px] text-muted-foreground">
                Continuously learning. Continuously improving.
              </span>
            </span>
          </Reveal>
        </div>

        {/* Mobile / tablet ecosystem */}
        <RevealGroup className="mt-12 grid gap-4 sm:grid-cols-2 lg:hidden" stagger={0.09}>
          <RevealItem className="flex items-center gap-3 rounded-md border border-brand/25 bg-brand/5 p-4 sm:col-span-2">
            <span className="grid h-12 w-12 shrink-0 place-items-center rounded-full bg-brand text-primary-foreground">
              <BellRing className="h-5 w-5" strokeWidth={1.7} aria-hidden />
            </span>
            <span className="min-w-0">
              <span className="block text-[11px] font-bold tracking-[0.16em] text-ink uppercase">
                One Event
              </span>
              <span className="mt-1 block text-[11.5px] text-muted-foreground">
                Everything begins with a single observation.
              </span>
            </span>
          </RevealItem>
          {[
            ...nodes,
            {
              key: "system",
              icon: ShieldCheck,
              title: "Smarter Safety System",
              copy: "Continuously learning. Continuously improving.",
            },
          ].map((node) => (
            <RevealItem
              key={node.key}
              className="flex items-start gap-3 rounded-md border border-border bg-card p-4 shadow-card"
            >
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full border border-border bg-secondary/50 text-brand">
                <node.icon className="h-[18px] w-[18px]" strokeWidth={1.7} aria-hidden />
              </span>
              <span className="min-w-0">
                <span className="block text-[10.5px] font-bold tracking-[0.14em] text-ink uppercase">
                  {node.title}
                </span>
                <span className="mt-1 block text-[11.5px] leading-relaxed text-muted-foreground">
                  {node.copy}
                </span>
              </span>
            </RevealItem>
          ))}
        </RevealGroup>

        <RevealGroup
          className="mt-16 flex flex-wrap items-center justify-center gap-x-12 gap-y-6 border-t border-border pt-10"
          stagger={0.12}
        >
          {principles.map((item) => (
            <RevealItem key={item.label} className="group flex items-center gap-2.5">
              <item.icon
                className="h-[18px] w-[18px] text-brand transition-transform duration-300 group-hover:scale-110"
                strokeWidth={1.8}
                aria-hidden
              />
              <span className="text-[13px] font-bold tracking-[0.12em] text-ink uppercase">
                {item.label}
              </span>
            </RevealItem>
          ))}
        </RevealGroup>
      </div>
    </section>
  );
}
