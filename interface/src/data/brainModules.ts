
export interface BrainModule {
  id: string;
  label: string;
  description: string;
  position: [number, number, number];
  color: number;
}

export const brainModules: BrainModule[] = [
  {
    id: "input",
    label: "INPUT",
    description: "Acquisition and interpretation of incoming signals.",
    position: [-2.2, 1.1, 0],
    color: 0x42a5f5,
  },
  {
    id: "memory",
    label: "MEMORY",
    description: "Storage and retrieval of information.",
    position: [2.2, 1.1, 0],
    color: 0x26c6da,
  },
  {
    id: "knowledge",
    label: "KNOWLEDGE",
    description: "Organization of structured knowledge.",
    position: [-2.2, -1.1, 0],
    color: 0x7e57c2,
  },
  {
    id: "reasoning",
    label: "REASONING",
    description: "Logical processing and inference.",
    position: [2.2, -1.1, 0],
    color: 0x66bb6a,
  },
  {
    id: "planning",
    label: "PLANNING",
    description: "Goal decomposition and planning.",
    position: [0, 2.2, 0],
    color: 0xffb74d,
  },
  {
    id: "learning",
    label: "LEARNING",
    description: "Learning from evaluated experience.",
    position: [0, -2.2, 0],
    color: 0xec407a,
  },
  {
    id: "metacognition",
    label: "METACOGNITION",
    description: "Monitoring and evaluating internal processes.",
    position: [-1.8, 0, 1.8],
    color: 0xab47bc,
  },
  {
    id: "execution",
    label: "EXECUTION",
    description: "Controlled execution of approved operations.",
    position: [1.8, 0, 1.8],
    color: 0xff7043,
  },
  {
    id: "evolution",
    label: "EVOLUTION",
    description: "Controlled experimentation and improvement.",
    position: [-1.8, 0, -1.8],
    color: 0x29b6f6,
  },
  {
    id: "validation",
    label: "VALIDATION",
    description: "Independent testing and validation.",
    position: [1.8, 0, -1.8],
    color: 0xd4e157,
  },
];
