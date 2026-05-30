const healuxaProposal = {
  brand: "Healuxa",
  positioning: "Luxury AI-powered Beauty, Health & Longevity Ecosystem in Dubai",
  mission:
    "Help users reach their most attractive and healthiest version through curated, data-driven and seamlessly managed care journeys.",
  coreValueProposition: [
    "Unified management of beauty, wellness, medical and lifestyle services",
    "Personalized roadmap with transparent steps, timeline and outcomes",
    "Concierge-level execution across app and WhatsApp"
  ],
  serviceCategories: [
    "Weight loss & fitness",
    "Botox, filler and aesthetic services",
    "Skin and hair care",
    "Nutrition and workout plans",
    "Checkups and lab tests",
    "Medication and treatment tracking",
    "Rejuvenation and longevity",
    "Medical consultation",
    "Home visit services",
    "Supplements and care products"
  ],
  productPillars: {
    personalizedRoadmap: true,
    curatedProviderMatching: true,
    smartScheduling: true,
    conciergeOperations: true,
    continuousLearningLoop: true
  },
  matchingEngine: {
    model: "Curated Provider Matching & Scheduling",
    factors: [
      "user need",
      "geo proximity",
      "provider quality score",
      "availability",
      "specialization fit",
      "service style fit",
      "user ratings"
    ]
  },
  mlStrategy: {
    phase1: "Rule-based + weighted ranking",
    phase2: "Learning-to-rank for personalization",
    phase3: "Outcome and adherence optimization"
  },
  targetApps: {
    mobile: ["iOS", "Android"],
    channels: ["Mobile App", "WhatsApp"],
    goals: ["Fast", "Luxury UX", "Highly scalable", "Transparent journey"]
  },
  architectureRecommendation: {
    mobile: "React Native (Expo) + TypeScript",
    backend: "FastAPI microservices + PostgreSQL + Redis + queue",
    ai: "Python ML services",
    infra: "Kubernetes + CI/CD + observability"
  },
  successKPIs: [
    "Activation rate",
    "Time to first booking",
    "Care-plan adherence",
    "Retention (30/60/90)",
    "Repeat booking",
    "NPS",
    "Provider quality index"
  ]
};

module.exports = healuxaProposal;
