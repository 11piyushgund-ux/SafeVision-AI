import { motion, useReducedMotion } from "motion/react";
import {
  Video,
  ScanSearch,
  ShieldAlert,
  BookOpen,
  BellRing,
  Database,
  LineChart,
  ChevronRight,
} from "lucide-react";
import { Reveal } from "./Reveal";

const steps = [
  {
    n: "01",
    name: "Monitor",
    icon: Video,
    copy: "Observe every critical environment in real time.",
  },
  {
    n: "02",
    name: "Detect",
    icon: ScanSearch,
    copy: "Identify safety events, unsafe actions, and hazards instantly.",
  },
  {
    n: "03",
    name: "Assess",
    icon: ShieldAlert,
    copy: "Evaluate severity, context, and risk level of each event.",
  },
  {
    n: "04",
    name: "Understand",
    icon: BookOpen,
    copy: "Connect the event with relevant safety knowledge and SOPs.",
  },
  {
    n: "05",
    name: "Respond",
    icon: BellRing,
    copy: "Generate intelligent recommendations and alert the right people.",
  },
  {
    n: "06",
    name: "Record",
    icon: Database,
    copy: "Store every event with evidence for compliance and future analysis.",
  },
  {
    n: "07",
    name: "Learn",
    icon: LineChart,
    copy: "Analyze trends and patterns to prevent future incidents.",
  },
];

export function HowItWorks() {
  const reduced = useReducedMotion();

  return (
    <section className="bg-canvas-warm py-16 sm:py-24">
      <div className="mx-auto max-w-[1340px] px-4 sm:px-6 lg:px-8">
        <Reveal className="text-center">
          <div className="flex items-center justify-center gap-3">
            <span className="h-px w-8 bg-brand/40" />
            <p className="eyebrow text-brand">How SafeVision AI Works</p>
            <span className="h-px w-8 bg-brand/40" />
          </div>
          <h2 className="display-title mx-auto mt-5 max-w-[22ch] text-[clamp(2rem,4.6vw,3.5rem)] text-ink">
            From Observation to <span className="text-brand">Intelligent Action.</span>
          </h2>
          <p className="mx-auto mt-6 max-w-[62ch] text-[13.5px] leading-relaxed text-muted-foreground">
            SafeVision AI transforms real-time observations into actionable safety intelligence that
            protects people, prevents incidents, and builds a safer workplace.
          </p>
        </Reveal>

        <motion.ol
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.2 }}
          variants={{ hidden: {}, visible: { transition: { staggerChildren: 0.16 } } }}
          className="mt-16 grid grid-cols-2 gap-y-12 sm:grid-cols-4 lg:grid-cols-7 lg:gap-y-0"
        >
          {steps.map((step, i) => (
            <motion.li
              key={step.name}
              variants={{
                hidden: reduced ? { opacity: 0 } : { opacity: 0, y: 22 },
                visible: {
                  opacity: 1,
                  y: 0,
                  transition: { duration: 0.6, ease: [0.22, 1, 0.36, 1] },
                },
              }}
              className="relative flex flex-col items-center px-2 text-center"
            >
              <p className="text-[20px] leading-none font-extrabold tracking-[-0.01em] text-brand">
                {step.n}
              </p>
              <p className="mt-2 text-[10px] font-bold tracking-[0.16em] text-ink uppercase">
                {step.name}
              </p>

              <div className="group relative mt-5 grid h-[74px] w-[74px] place-items-center">
                <svg viewBox="0 0 74 74" className="absolute inset-0 h-full w-full" aria-hidden>
                  <circle
                    cx="37"
                    cy="37"
                    r="35.5"
                    fill="var(--card)"
                    stroke="var(--border)"
                    strokeWidth="1"
                  />
                  <motion.circle
                    cx="37"
                    cy="37"
                    r="35.5"
                    fill="none"
                    stroke="var(--brand)"
                    strokeWidth="1.6"
                    strokeLinecap="round"
                    strokeDasharray="223"
                    transform="rotate(-90 37 37)"
                    variants={{
                      hidden: { strokeDashoffset: 223 },
                      visible: {
                        strokeDashoffset: 78,
                        transition: { duration: 1.1, ease: [0.22, 1, 0.36, 1] },
                      },
                    }}
                  />
                </svg>
                <step.icon
                  className="relative h-7 w-7 text-ink transition-transform duration-300 group-hover:scale-110"
                  strokeWidth={1.5}
                  aria-hidden
                />
              </div>

              {i < steps.length - 1 ? (
                <motion.span
                  variants={{
                    hidden: { opacity: 0, scale: 0.6 },
                    visible: { opacity: 1, scale: 1, transition: { duration: 0.4 } },
                  }}
                  className="absolute top-[92px] -right-3 z-10 hidden h-5 w-5 place-items-center rounded-full border border-brand/40 bg-card text-brand lg:grid"
                  aria-hidden
                >
                  <ChevronRight className="h-3 w-3" strokeWidth={2.4} />
                </motion.span>
              ) : null}

              <p className="mt-5 max-w-[22ch] text-[11.5px] leading-relaxed text-muted-foreground">
                {step.copy}
              </p>
            </motion.li>
          ))}
        </motion.ol>

        <Reveal className="mt-16 flex items-center gap-4" delay={0.1}>
          <span className="h-px flex-1 bg-border" />
          <span className="h-2 w-2 rounded-full bg-brand" />
          <span className="h-px flex-1 bg-border" />
        </Reveal>
      </div>
    </section>
  );
}
