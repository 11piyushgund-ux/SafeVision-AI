import type { RiskLevel } from "@/data/safety-insights";

export type EventStatus = "Open" | "In Review" | "Resolved";

export type SafetyEvent = {
  id: string;
  type: string;
  location: string;
  timestamp: string;
  confidence: number;
  risk: RiskLevel;
  status: EventStatus;
};

export const eventTypes = [
  "All",
  "PPE Non-Compliance",
  "Slip and Fall Risk",
  "Fire Hazard",
  "Unsafe Material Handling",
  "Crowding in Area",
];

export const eventLocations = [
  "All",
  "Packaging Area",
  "Assembly Line 1",
  "Assembly Line 2",
  "Electrical Room",
  "Material Storage Zone",
  "Production Area",
];

export const riskLevels = ["All", "High", "Medium", "Low"];
export const eventStatuses = ["All", "Open", "In Review", "Resolved"];

export const totalEvents = 132;
export const totalEventPages = 14;

export const safetyEvents: SafetyEvent[] = [
  {
    id: "EVT-2025-0001",
    type: "PPE Non-Compliance",
    location: "Packaging Area",
    timestamp: "May 24, 2025 10:24 AM",
    confidence: 95,
    risk: "High",
    status: "Open",
  },
  {
    id: "EVT-2025-0002",
    type: "Slip and Fall Risk",
    location: "Assembly Line 2",
    timestamp: "May 24, 2025 09:12 AM",
    confidence: 90,
    risk: "Medium",
    status: "Open",
  },
  {
    id: "EVT-2025-0003",
    type: "Fire Hazard",
    location: "Electrical Room",
    timestamp: "May 23, 2025 06:45 PM",
    confidence: 93,
    risk: "High",
    status: "In Review",
  },
  {
    id: "EVT-2025-0004",
    type: "Unsafe Material Handling",
    location: "Material Storage Zone",
    timestamp: "May 23, 2025 03:30 PM",
    confidence: 88,
    risk: "Medium",
    status: "Open",
  },
  {
    id: "EVT-2025-0005",
    type: "PPE Non-Compliance",
    location: "Packaging Area",
    timestamp: "May 22, 2025 11:15 AM",
    confidence: 92,
    risk: "High",
    status: "Resolved",
  },
  {
    id: "EVT-2025-0006",
    type: "Crowding in Area",
    location: "Production Area",
    timestamp: "May 22, 2025 10:05 AM",
    confidence: 85,
    risk: "Low",
    status: "Resolved",
  },
  {
    id: "EVT-2025-0007",
    type: "PPE Non-Compliance",
    location: "Packaging Area",
    timestamp: "May 21, 2025 04:20 PM",
    confidence: 94,
    risk: "High",
    status: "Resolved",
  },
  {
    id: "EVT-2025-0008",
    type: "Unsafe Material Handling",
    location: "Material Storage Zone",
    timestamp: "May 21, 2025 02:40 PM",
    confidence: 87,
    risk: "Medium",
    status: "Resolved",
  },
  {
    id: "EVT-2025-0009",
    type: "Fire Hazard",
    location: "Electrical Room",
    timestamp: "May 20, 2025 05:10 PM",
    confidence: 90,
    risk: "High",
    status: "In Review",
  },
  {
    id: "EVT-2025-0010",
    type: "Slip and Fall Risk",
    location: "Assembly Line 1",
    timestamp: "May 20, 2025 09:30 AM",
    confidence: 89,
    risk: "Medium",
    status: "Resolved",
  },
];
