import {
  MessageSquare,
  Clock,
  Shield,
  Radio,
  Database,
  Server,
  GitBranch,
  GitCommit,
  Layers,
  Users,
} from 'lucide-react';

interface Project {
  id: string;
  name: string;
  description: string;
  difficulty: 'beginner' | 'intermediate' | 'advanced';
  icon: React.ReactNode;
}

const projects: Project[] = [
  {
    id: 'two-generals',
    name: 'Two Generals Problem',
    description: 'Explore the impossibility of reliable communication over unreliable channels',
    difficulty: 'beginner',
    icon: <MessageSquare size={20} />,
  },
  {
    id: 'clocks',
    name: 'Logical & Physical Clocks',
    description: 'Understand Lamport timestamps and Vector clocks for event ordering',
    difficulty: 'beginner',
    icon: <Clock size={20} />,
  },
  {
    id: 'byzantine',
    name: 'Byzantine Generals',
    description: 'Handle malicious actors with Byzantine fault tolerance (3f+1)',
    difficulty: 'intermediate',
    icon: <Shield size={20} />,
  },
  {
    id: 'broadcast',
    name: 'Broadcast Protocols',
    description: 'FIFO, Causal, and Total Order broadcast algorithms',
    difficulty: 'intermediate',
    icon: <Radio size={20} />,
  },
  {
    id: 'quorum',
    name: 'Quorum Systems',
    description: 'Read/Write quorums ensuring consistency with W+R>N',
    difficulty: 'intermediate',
    icon: <Database size={20} />,
  },
  {
    id: 'state-machine',
    name: 'State Machine Replication',
    description: 'Replicated logs with deterministic state transitions',
    difficulty: 'intermediate',
    icon: <Server size={20} />,
  },
  {
    id: 'raft',
    name: 'Raft Consensus',
    description: 'Leader election, log replication, and safety guarantees',
    difficulty: 'advanced',
    icon: <GitBranch size={20} />,
  },
  {
    id: 'two-phase-commit',
    name: 'Two-Phase Commit',
    description: 'Distributed transactions with atomic commit protocol',
    difficulty: 'advanced',
    icon: <GitCommit size={20} />,
  },
  {
    id: 'consistency',
    name: 'Consistency Models',
    description: 'Compare Linearizability, Sequential, and Eventual consistency',
    difficulty: 'advanced',
    icon: <Layers size={20} />,
  },
  {
    id: 'crdt',
    name: 'CRDTs',
    description: 'Conflict-free Replicated Data Types for collaboration',
    difficulty: 'advanced',
    icon: <Users size={20} />,
  },
];

interface ProjectSelectorProps {
  onSelect: (projectId: string) => void;
  currentProject: string | null;
}

export function ProjectSelector({ onSelect, currentProject }: ProjectSelectorProps) {
  return (
    <div className="project-selector">
      <h2>Select a Project</h2>
      <p className="project-selector-subtitle">
        Choose a distributed systems concept to explore through interactive visualization
      </p>
      <div className="project-grid">
        {projects.map((project) => (
          <div
            key={project.id}
            className={`project-card ${currentProject === project.id ? 'selected' : ''}`}
            onClick={() => onSelect(project.id)}
          >
            <div className={`project-icon ${project.difficulty}`}>
              {project.icon}
            </div>
            <div className="project-header">
              <h3>{project.name}</h3>
              <span className={`difficulty-badge ${project.difficulty}`}>
                {project.difficulty}
              </span>
            </div>
            <p>{project.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
