import type { RiskLevel } from "@/data/safety-insights";

const riskDot: Record<RiskLevel, string> = {
  High: "bg-risk-high",
  Medium: "bg-risk-medium",
  Low: "bg-risk-low",
};

const riskText: Record<RiskLevel, string> = {
  High: "text-risk-high",
  Medium: "text-risk-medium",
  Low: "text-risk-low",
};

const riskChip: Record<RiskLevel, string> = {
  High: "bg-risk-high-soft text-risk-high",
  Medium: "bg-risk-medium-soft text-risk-medium",
  Low: "bg-risk-low-soft text-risk-low",
};

export function RiskDotLabel({ risk }: { risk: RiskLevel }) {
  return (
    <span className={`inline-flex items-center gap-1.5 text-[13px] font-medium ${riskText[risk]}`}>
      <span className={`h-2 w-2 rounded-full ${riskDot[risk]}`} />
      {risk} Risk
    </span>
  );
}

export function RiskChip({ risk, label }: { risk: RiskLevel; label?: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-md px-2.5 py-1 text-[13px] font-medium ${riskChip[risk]}`}
    >
      {label ?? `${risk} Risk`}
    </span>
  );
}
