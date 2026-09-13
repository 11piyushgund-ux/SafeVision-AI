export type RiskLevel = "High" | "Medium" | "Low";

export type HistoricalEvent = {
  date: string;
  time: string;
  description: string;
  location: string;
  risk: RiskLevel;
  outcome: string;
};

export type RecommendationAction = {
  id: string;
  priority: "Immediate" | "Short-term" | "Long-term";
  title: string;
  description: string;
  owner: string;
  targetDate: string;
  expectedOutcome: string;
};

export type SafetyInsight = {
  id: string;
  title: string;
  risk: RiskLevel;
  summary: string;
  date: string;
  time: string;
  icon: "helmet" | "slip" | "fire" | "box" | "crowd";
  generatedAt: string;
  analysis: {
    eventSummary: string;
    riskAssessment: string;
    contributingFactors: string[];
  };
  recommendations: {
    strategicObjective: string;
    executiveSummary: string;
    complianceStandard: string;
    actions: RecommendationAction[];
    preventiveGuidance: string[];
  };
  safetyInformation: {
    policyTitle: string;
    source: string;
    policyText: string;
    keyRequirements: string[];
  };
  historicalContext: HistoricalEvent[];
};

export const safetyInsights: SafetyInsight[] = [
  {
    id: "ppe-packaging",
    title: "PPE Non-Compliance in Packaging Area",
    risk: "High",
    summary: "Multiple PPE violations detected in Packaging Area during morning shifts.",
    date: "May 24",
    time: "10:24 AM",
    icon: "helmet",
    generatedAt: "May 24, 2025 at 10:24 AM",
    analysis: {
      eventSummary:
        "Between May 18 – May 24, 2025, multiple PPE non-compliance events were detected in the Packaging Area, especially during the morning shifts (08:00 AM – 11:00 AM).",
      riskAssessment:
        "Workers are repeatedly not wearing mandatory PPE (safety helmet, gloves). This increases the probability of head injuries and hand injuries.",
      contributingFactors: [
        "Low PPE compliance during morning shifts",
        "Insufficient supervision in the area",
        "Workers not following PPE protocol",
        "High workload during peak hours",
      ],
    },
    recommendations: {
      strategicObjective: "Achieve 100% PPE compliance across Packaging Lines 1-4 within 48 hours.",
      executiveSummary:
        "AI recommends immediate checkpoint enforcement at shift start combined with optical gate alerts, followed by supervisor spot-audits and automated compliance logging.",
      complianceStandard: "OSHA 1910.132 (General PPE) & ISO 45001 Clause 8.1.2",
      actions: [
        {
          id: "rec-ppe-1",
          priority: "Immediate",
          title: "Mandatory Shift-Start PPE Checkpoint",
          description: "Station shift safety supervisor at Packaging Area Entry point to conduct physical verification before workers enter the active operational zone.",
          owner: "Shift Supervisor (Packaging)",
          targetDate: "Today (Next Shift)",
          expectedOutcome: "Zero workers enter zone without helmet and mandatory cut-resistant gloves.",
        },
        {
          id: "rec-ppe-2",
          priority: "Short-term",
          title: "Install Automated Audio-Visual Compliance Gate",
          description: "Enable automated warning strobe and audible reminder at camera feed zone perimeter whenever missing helmet is detected.",
          owner: "Automation Engineering Team",
          targetDate: "Within 3 Days",
          expectedOutcome: "Immediate automated worker self-correction upon crossing zone perimeter.",
        },
        {
          id: "rec-ppe-3",
          priority: "Long-term",
          title: "Shift-Specific Safety Briefing & Accountability Review",
          description: "Hold focused 10-minute toolbox talk covering recent incidents with morning crew; introduce supervisor weekly compliance KPI tracking.",
          owner: "HSE Department Lead",
          targetDate: "End of Week",
          expectedOutcome: "Sustainable shift compliance rate improvement from 82% to >99%.",
        },
      ],
      preventiveGuidance: [
        "Place spare PPE station immediately adjacent to the packaging line entrance.",
        "Include helmet compliance metrics in the daily operational stand-up dashboard.",
        "Implement buddy-check verification protocol for workers operating conveyor machinery.",
      ],
    },
    safetyInformation: {
      policyTitle: "PPE Usage Policy – Section 4.2",
      source: "Safety Knowledge Base",
      policyText:
        "All workers must wear appropriate PPE at all times in the production and packaging areas.",
      keyRequirements: [
        "Safety helmet must be worn in all production and packaging zones.",
        "Safety gloves must be worn while handling materials or operating machines.",
        "Safety shoes must be worn to protect against slip, fall, and heavy object impact.",
        "Supervisors must ensure 100% PPE compliance during every shift.",
        "Non-compliance may result in disciplinary action as per company policy.",
      ],
    },
    historicalContext: [
      { date: "May 22, 2025", time: "09:18 AM", description: "PPE non-compliance detected in Packaging Area", location: "Packaging Area", risk: "High", outcome: "Warning issued" },
      { date: "May 20, 2025", time: "10:05 AM", description: "PPE non-compliance detected in Packaging Area", location: "Packaging Area", risk: "High", outcome: "Warning issued" },
      { date: "May 18, 2025", time: "08:47 AM", description: "PPE non-compliance detected in Packaging Area", location: "Packaging Area", risk: "Medium", outcome: "Counseling provided" },
      { date: "May 17, 2025", time: "02:15 PM", description: "PPE non-compliance detected in Packaging Area", location: "Packaging Area", risk: "Medium", outcome: "Counseling provided" },
      { date: "May 16, 2025", time: "11:32 AM", description: "PPE non-compliance detected in Packaging Area", location: "Packaging Area", risk: "Medium", outcome: "Warning issued" },
    ],
  },
  {
    id: "slip-assembly",
    title: "Slip and Fall Risk in Assembly Line",
    risk: "Medium",
    summary: "Wet floor conditions repeatedly detected near Assembly Line 2.",
    date: "May 24",
    time: "09:12 AM",
    icon: "slip",
    generatedAt: "May 24, 2025 at 09:12 AM",
    analysis: {
      eventSummary:
        "Between May 19 – May 24, 2025, wet floor conditions were repeatedly detected near Assembly Line 2, primarily after cleaning cycles.",
      riskAssessment:
        "Persistent wet surfaces in a high-traffic walkway increase the probability of slip and fall injuries, including sprains and fractures.",
      contributingFactors: [
        "Delayed drying after cleaning cycles",
        "Missing wet floor signage",
        "Frequent liquid spillage near the line",
        "High foot traffic during shift change",
      ],
    },
    recommendations: {
      strategicObjective: "Eliminate slip-and-fall hazards along Assembly corridor and ensure dry walking surfaces within 5 minutes of washdowns.",
      executiveSummary:
        "AI recommends deploying rapid-dry blower stations, rescheduling deep washdowns to shift change breaks, and installing permanent textured anti-slip runners.",
      complianceStandard: "OSHA 1910.22 (Walking-Working Surfaces) & ISO 45001",
      actions: [
        {
          id: "rec-slip-1",
          priority: "Immediate",
          title: "Deploy Physical Barriers & High-Visibility Cones",
          description: "Place high-visibility cautionary wet floor cones immediately surrounding wet spots near Line 2 until drying is certified.",
          owner: "Sanitation Lead / Line 2 Supervisor",
          targetDate: "Immediate",
          expectedOutcome: "Immediate hazard awareness; diversion of worker traffic around slick zones.",
        },
        {
          id: "rec-slip-2",
          priority: "Short-term",
          title: "Reschedule Cleaning to 20-Minute Pre-Shift Gap",
          description: "Shift floor wet-scrubbing schedule by 30 minutes so that floor surfaces dry completely before primary worker transit begins.",
          owner: "Facilities Maintenance",
          targetDate: "Within 24 Hours",
          expectedOutcome: "Foot traffic eliminated during active floor drying periods.",
        },
        {
          id: "rec-slip-3",
          priority: "Long-term",
          title: "Install Modular Anti-Fatigue Drainage Mats",
          description: "Procure and fit chemical-resistant grooved drainage runners along the entire 45-meter Line 2 operator walkway.",
          owner: "Plant Operations Manager",
          targetDate: "Next Maintenance Shutdown",
          expectedOutcome: "90% reduction in surface moisture accumulation under normal operations.",
        },
      ],
      preventiveGuidance: [
        "Mandate slip-resistant footwear with certified SRC grip ratings for all assembly staff.",
        "Implement a 3-minute rapid spill cleanup response protocol with dedicated mop stations.",
      ],
    },
    safetyInformation: {
      policyTitle: "Floor Safety Procedure – Section 2.6",
      source: "Safety Knowledge Base",
      policyText:
        "All walkways and production floors must be kept dry, clear, and clearly marked whenever a slip hazard is present.",
      keyRequirements: [
        "Wet floor signage must be placed immediately after any spill or cleaning.",
        "Spills must be cleaned within 5 minutes of detection.",
        "Anti-slip footwear must be worn in all assembly zones.",
        "Cleaning cycles must be scheduled outside peak movement hours.",
        "Supervisors must verify floor condition at the start of every shift.",
      ],
    },
    historicalContext: [
      { date: "May 22, 2025", time: "08:40 AM", description: "Wet floor detected near Assembly Line 2", location: "Assembly Line 2", risk: "Medium", outcome: "Area cleaned" },
      { date: "May 21, 2025", time: "01:12 PM", description: "Slip hazard detected near Assembly Line 2", location: "Assembly Line 2", risk: "Medium", outcome: "Signage placed" },
      { date: "May 19, 2025", time: "09:55 AM", description: "Wet floor detected near Assembly Line 2", location: "Assembly Line 2", risk: "Low", outcome: "Monitoring continued" },
    ],
  },
  {
    id: "fire-electrical",
    title: "Fire Hazard in Electrical Room",
    risk: "High",
    summary: "Overheating equipment detected multiple times in Electrical Room.",
    date: "May 23",
    time: "06:45 PM",
    icon: "fire",
    generatedAt: "May 23, 2025 at 06:45 PM",
    analysis: {
      eventSummary:
        "Between May 20 – May 23, 2025, elevated equipment temperatures were detected multiple times in the Electrical Room during evening hours.",
      riskAssessment:
        "Repeated overheating of electrical panels significantly increases the probability of short circuits and fire incidents.",
      contributingFactors: [
        "Inadequate ventilation in the Electrical Room",
        "Overloaded distribution panels",
        "Delayed preventive maintenance",
        "Ambient temperature rise during evening operations",
      ],
    },
    recommendations: {
      strategicObjective: "Bring Electrical Room panel temperatures below 45°C and eliminate short-circuit fire hazards immediately.",
      executiveSummary:
        "AI recommends instant auxiliary cooling deployment, thermal imaging inspection of Distribution Panel B, and rebalancing line phase loads.",
      complianceStandard: "NFPA 70E / OSHA 1910.303 (Electrical Safety Standards)",
      actions: [
        {
          id: "rec-fire-1",
          priority: "Immediate",
          title: "Deploy Portable Industrial Spot Air Conditioner",
          description: "Position mobile spot chiller directly targeting Panel B intake vents to suppress thermal buildup pending HVAC repair.",
          owner: "Facilities Maintenance Electrician",
          targetDate: "Immediate (< 2 Hours)",
          expectedOutcome: "Panel ambient temperature reduced from 58°C to < 40°C within 60 minutes.",
        },
        {
          id: "rec-fire-2",
          priority: "Immediate",
          title: "Certified FLIR Infrared Thermography Inspection",
          description: "Perform comprehensive thermal scan across all circuit connections and busbars to pinpoint loose terminals or phase imbalance.",
          owner: "Master Electrician",
          targetDate: "Today (Evening Shift)",
          expectedOutcome: "Identify and torque loose terminations responsible for resistance heating.",
        },
        {
          id: "rec-fire-3",
          priority: "Short-term",
          title: "Substation Feeder Load Rebalancing",
          description: "Re-route high-draw induction motor loads from Panel B to auxiliary Sub-Panel 4 to maintain total draw below 75% capacity.",
          owner: "Electrical Engineering Lead",
          targetDate: "Tomorrow 08:00 AM",
          expectedOutcome: "Long-term thermal stabilization below operating limits.",
        },
      ],
      preventiveGuidance: [
        "Verify zero combustible materials or storage boxes within 36-inch clearance radius of all switchgear.",
        "Configure automated thermal sensor alerts to notify plant safety lead when panel temp exceeds 50°C.",
      ],
    },
    safetyInformation: {
      policyTitle: "Electrical Safety Policy – Section 6.1",
      source: "Safety Knowledge Base",
      policyText:
        "Electrical rooms must be maintained within safe operating temperature limits and kept free of combustible material.",
      keyRequirements: [
        "Panel temperature must be inspected daily during operations.",
        "Ventilation systems must remain unobstructed at all times.",
        "No combustible materials may be stored in electrical rooms.",
        "Thermal inspection must be conducted monthly.",
        "Any overheating event must be reported immediately.",
      ],
    },
    historicalContext: [
      { date: "May 22, 2025", time: "07:10 PM", description: "Overheating detected in Electrical Room", location: "Electrical Room", risk: "High", outcome: "Maintenance notified" },
      { date: "May 21, 2025", time: "06:20 PM", description: "Panel temperature above threshold", location: "Electrical Room", risk: "Medium", outcome: "Load rebalanced" },
      { date: "May 20, 2025", time: "05:48 PM", description: "Overheating detected in Electrical Room", location: "Electrical Room", risk: "High", outcome: "Inspection completed" },
    ],
  },
  {
    id: "material-handling",
    title: "Unsafe Material Handling",
    risk: "Medium",
    summary: "Improper lifting posture detected frequently in Material Storage Zone.",
    date: "May 23",
    time: "03:30 PM",
    icon: "box",
    generatedAt: "May 23, 2025 at 03:30 PM",
    analysis: {
      eventSummary:
        "Between May 18 – May 23, 2025, improper lifting postures were frequently detected in the Material Storage Zone during afternoon shifts.",
      riskAssessment:
        "Repeated incorrect lifting posture increases the probability of back strain and long-term musculoskeletal injuries.",
      contributingFactors: [
        "Manual handling of heavy loads",
        "Lifting aids not consistently used",
        "Limited ergonomics training",
        "Time pressure during dispatch windows",
      ],
    },
    recommendations: {
      strategicObjective: "Prevent musculoskeletal back injuries by instituting mechanical lift assists and ergonomic lifting techniques.",
      executiveSummary:
        "AI recommends enforcing a 20 kg manual lift cutoff, reconfiguring storage racking heights, and providing hands-on ergonomic coaching.",
      complianceStandard: "NIOSH Manual Material Handling / ISO 11228-1",
      actions: [
        {
          id: "rec-mat-1",
          priority: "Immediate",
          title: "Mandatory Two-Person Lift / Scissor Cart Usage",
          description: "Enforce strict team-lift rule for all parcels over 20 kg; move hydraulic scissor carts to active storage aisles.",
          owner: "Warehouse Logistics Supervisor",
          targetDate: "Immediate",
          expectedOutcome: "Elimination of solo manual handling of oversized pallets and heavy cartons.",
        },
        {
          id: "rec-mat-2",
          priority: "Short-term",
          title: "Aisle Pallet Rack Height Reconfiguration",
          description: "Re-slot heavy inventory (>15 kg) between knuckle and shoulder height (75 cm – 120 cm) to eliminate ground-level bending.",
          owner: "Inventory Control Manager",
          targetDate: "Within 4 Days",
          expectedOutcome: "65% reduction in high-risk deep bending lifts during order picking.",
        },
        {
          id: "rec-mat-3",
          priority: "Long-term",
          title: "Practical Biomechanics Coaching Session",
          description: "Schedule on-site physiotherapist to conduct 15-minute practical ergonomic posture sessions for all afternoon handlers.",
          owner: "Occupational Health & Safety",
          targetDate: "Next Friday",
          expectedOutcome: "Documented certification and behavioral correction across 100% of warehouse staff.",
        },
      ],
      preventiveGuidance: [
        "Inspect hydraulic pallet trucks weekly to ensure smooth roll resistance.",
        "Implement micro-rest stretch breaks during high-volume afternoon dispatch windows.",
      ],
    },
    safetyInformation: {
      policyTitle: "Manual Handling Policy – Section 3.4",
      source: "Safety Knowledge Base",
      policyText:
        "All manual lifting must follow approved ergonomic techniques, and mechanical aids must be used for heavy loads.",
      keyRequirements: [
        "Loads above 20 kg must be handled with mechanical aids.",
        "Workers must bend at the knees and keep the back straight.",
        "Team lifting is required for bulky or awkward loads.",
        "Ergonomics refresher training must be completed annually.",
        "Storage racks must keep heavy items at waist height.",
      ],
    },
    historicalContext: [
      { date: "May 21, 2025", time: "03:05 PM", description: "Improper lifting posture detected", location: "Material Storage Zone", risk: "Medium", outcome: "Counseling provided" },
      { date: "May 19, 2025", time: "04:22 PM", description: "Manual handling of heavy load detected", location: "Material Storage Zone", risk: "Medium", outcome: "Lifting aid assigned" },
      { date: "May 18, 2025", time: "02:50 PM", description: "Improper lifting posture detected", location: "Material Storage Zone", risk: "Low", outcome: "Verbal reminder" },
    ],
  },
  {
    id: "crowding-production",
    title: "Crowding in Production Area",
    risk: "Low",
    summary: "High density of workers detected in Production Area during shift change.",
    date: "May 22",
    time: "11:15 AM",
    icon: "crowd",
    generatedAt: "May 22, 2025 at 11:15 AM",
    analysis: {
      eventSummary:
        "Between May 18 – May 22, 2025, high worker density was detected in the Production Area during shift change windows.",
      riskAssessment:
        "Crowding in walkways reduces safe movement space and slightly increases the probability of collisions and congestion during evacuation.",
      contributingFactors: [
        "Overlapping shift change timings",
        "Single main entry and exit route",
        "Narrow walkway near production lines",
        "Gathering near the attendance point",
      ],
    },
    recommendations: {
      strategicObjective: "Decentralize pedestrian movement during shift turnovers and preserve 2.5-meter clear clearance in main aisleways.",
      executiveSummary:
        "AI recommends staggering clock-in intervals by 10 minutes, marking one-way traffic lanes, and opening secondary facility turnstiles.",
      complianceStandard: "OSHA 1910.36 (Design and Construction Requirements for Exit Routes)",
      actions: [
        {
          id: "rec-crowd-1",
          priority: "Immediate",
          title: "Designate One-Way Pedestrian Flow Lanes",
          description: "Apply floor visual tape demarcating separate entry and exit corridors along the main production artery.",
          owner: "Floor Operations Supervisor",
          targetDate: "Today",
          expectedOutcome: "Elimination of head-on pedestrian congestion during shift turnovers.",
        },
        {
          id: "rec-crowd-2",
          priority: "Short-term",
          title: "10-Minute Staggered Shift Change Schedule",
          description: "Offset Line A and Line B relief clock-in times by 10 minutes to smooth peak transit volume through the primary hallway.",
          owner: "Production Planning Dept",
          targetDate: "Starting Monday",
          expectedOutcome: "50% reduction in peak corridor density between 11:00 AM and 11:20 AM.",
        },
        {
          id: "rec-crowd-3",
          priority: "Long-term",
          title: "Commission Secondary Attendance Kiosks at South Bay",
          description: "Activate secondary badge swipe terminals at South Gate to distribute foot traffic across two facility exits.",
          owner: "IT / HR Systems Team",
          targetDate: "Within 2 Weeks",
          expectedOutcome: "Permanently resolved choke-point at main attendance station.",
        },
      ],
      preventiveGuidance: [
        "Strictly prohibit congregating in marked yellow emergency egress zones.",
        "Ensure all emergency doors remain free from temporary carts or material staging.",
      ],
    },
    safetyInformation: {
      policyTitle: "Workplace Movement Policy – Section 5.3",
      source: "Safety Knowledge Base",
      policyText:
        "Walkways and shift-change routes must remain clear to allow safe worker movement and emergency evacuation.",
      keyRequirements: [
        "Designated walkways must never be blocked.",
        "Shift changes should be staggered where possible.",
        "Emergency exit routes must remain fully accessible.",
        "Gathering in production walkways is not permitted.",
        "Supervisors must manage flow during peak movement times.",
      ],
    },
    historicalContext: [
      { date: "May 21, 2025", time: "11:10 AM", description: "High worker density during shift change", location: "Production Area", risk: "Low", outcome: "Flow managed" },
      { date: "May 20, 2025", time: "11:05 AM", description: "Crowding detected near entry route", location: "Production Area", risk: "Low", outcome: "Monitoring continued" },
      { date: "May 18, 2025", time: "10:58 AM", description: "High worker density during shift change", location: "Production Area", risk: "Medium", outcome: "Shift stagger advised" },
    ],
  },
];

export const totalInsights = 12;
export const totalPages = 3;
