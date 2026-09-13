import { Boxes, Flame, HardHat, PersonStanding, Users } from "lucide-react";

export type InsightIconName = "helmet" | "slip" | "fire" | "box" | "crowd";

const map = {
  helmet: { Icon: HardHat, wrap: "bg-ai-soft", color: "text-ai" },
  slip: { Icon: PersonStanding, wrap: "bg-risk-medium-soft", color: "text-risk-medium" },
  fire: { Icon: Flame, wrap: "bg-risk-high-soft", color: "text-risk-high" },
  box: { Icon: Boxes, wrap: "bg-risk-low-soft", color: "text-risk-low" },
  crowd: { Icon: Users, wrap: "bg-primary-soft", color: "text-primary" },
} as const;

export function InsightIcon({
  icon,
  size = "sm",
}: {
  icon: InsightIconName;
  size?: "sm" | "lg";
}) {
  const { Icon, wrap, color } = map[icon];
  const box = size === "lg" ? "h-14 w-14 rounded-2xl" : "h-11 w-11 rounded-full";
  const glyph = size === "lg" ? "h-7 w-7" : "h-5 w-5";
  return (
    <span className={`flex shrink-0 items-center justify-center ${box} ${wrap}`}>
      <Icon className={`${glyph} ${color}`} strokeWidth={1.8} />
    </span>
  );
}
