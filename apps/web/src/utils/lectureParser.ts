// Lecture content types and parser

export interface LectureTimestamp {
  time: string;
  link: string;
  description: string;
}

export interface LectureSection {
  title: string;
  content: string;
  quotes: string[];
  timestamp?: LectureTimestamp;
}

export interface LectureContent {
  title: string;
  videoUrl: string;
  videoId: string;
  overview: string;
  sections: LectureSection[];
  conclusion: string;
  tags: string[];
}

// Map project IDs to their lecture files
export const projectToLectureMapping: Record<string, string[]> = {
  'two-generals': ['2_1_two_generals_problem'],
  'byzantine': ['2_2_byzantine_generals_problem'],
  'clocks': ['4_1_logical_time', '3_3_causality_and_happens_before'],
  'broadcast': ['4_2_broadcast_ordering', '4_3_broadcast_algorithms'],
  'raft': ['6_2_raft', '6_1_consensus'],
  'quorum': ['5_2_quorums'],
  'state-machine': ['5_3_state_machine_replication'],
  'two-phase-commit': ['7_1_two_phase_commit'],
  'consistency': ['7_2_linearizability', '7_3_eventual_consistency'],
  'crdt': ['8_1_collaboration_software'],
};

// Static lecture content (embedded for simplicity)
export const lectureContent: Record<string, LectureContent> = {
  'two-generals': {
    title: 'The Two Generals Problem',
    videoUrl: 'https://www.youtube.com/watch?v=MDuWnzVnfpI',
    videoId: 'MDuWnzVnfpI',
    overview: 'The Two Generals Problem illustrates the impossibility of achieving guaranteed consensus in unreliable networks. Two generals must coordinate an attack, but their messengers may be captured. This demonstrates why distributed systems cannot achieve perfect certainty.',
    tags: ['consensus', 'impossibility', 'fault-tolerance'],
    sections: [
      {
        title: 'The Problem',
        content: 'Two generals must coordinate to attack simultaneously. They can only communicate via messengers who might be captured. Neither general knows if their message arrived.',
        quotes: [
          'The two generals can\'t just talk to each other... they can only communicate via messengers that might get captured.',
        ],
        timestamp: {
          time: '0:00',
          link: 'https://youtu.be/MDuWnzVnfpI?t=0',
          description: 'Introduction to the problem',
        },
      },
      {
        title: 'Infinite Regress',
        content: 'Even if General 1 receives an acknowledgment, they don\'t know if their ACK-of-ACK was received. This leads to infinite chains of confirmations, yet certainty is never achieved.',
        quotes: [
          'You end up with infinite chains of messages before there\'s any certainty.',
          'General one does not know whether the initial message didn\'t get through or the response was lost.',
        ],
        timestamp: {
          time: '2:00',
          link: 'https://youtu.be/MDuWnzVnfpI?t=120',
          description: 'Analyzing infinite regress',
        },
      },
      {
        title: 'Real-World Application',
        content: 'In e-commerce, a shop and payment service face the same problem. The solution: make actions revocable (refunds) and use idempotent operations that can be safely retried.',
        quotes: [
          'The online shop dispatches goods if and only if the payment service charges the card... analogous to the two generals problem.',
        ],
        timestamp: {
          time: '7:43',
          link: 'https://youtu.be/MDuWnzVnfpI?t=463',
          description: 'Practical applications',
        },
      },
    ],
    conclusion: 'Perfect consensus is impossible in unreliable networks, but real systems use revocable actions and idempotency to achieve eventual consistency.',
  },

  'byzantine': {
    title: 'Byzantine Generals Problem',
    videoUrl: 'https://www.youtube.com/watch?v=LoGx_ldRBU0',
    videoId: 'LoGx_ldRBU0',
    overview: 'The Byzantine Generals Problem extends the two generals problem to include malicious (Byzantine) nodes that may send conflicting messages. The key insight: consensus requires at least 3f+1 nodes to tolerate f Byzantine failures.',
    tags: ['byzantine', 'fault-tolerance', 'consensus'],
    sections: [
      {
        title: 'Byzantine Faults',
        content: 'Unlike crash faults where nodes simply stop, Byzantine faults involve nodes that actively behave maliciously - sending conflicting messages to different parties.',
        quotes: [
          'A Byzantine node might send different values to different recipients.',
        ],
        timestamp: {
          time: '0:00',
          link: 'https://youtu.be/LoGx_ldRBU0?t=0',
          description: 'Introduction to Byzantine faults',
        },
      },
      {
        title: 'The 3f+1 Requirement',
        content: 'To tolerate f Byzantine nodes, you need at least 3f+1 total nodes. With fewer nodes, traitors can always cause disagreement among honest nodes.',
        quotes: [
          'With 3 nodes and 1 traitor, the honest nodes cannot distinguish between conflicting claims.',
        ],
        timestamp: {
          time: '5:00',
          link: 'https://youtu.be/LoGx_ldRBU0?t=300',
          description: 'Proving the 3f+1 bound',
        },
      },
      {
        title: 'Oral Messages Algorithm',
        content: 'The OM(m) algorithm solves Byzantine consensus in m+1 rounds for m traitors. Nodes exchange values and use majority voting to reach agreement.',
        quotes: [
          'Each lieutenant relays what they received, and majority voting determines the final decision.',
        ],
        timestamp: {
          time: '10:00',
          link: 'https://youtu.be/LoGx_ldRBU0?t=600',
          description: 'The OM algorithm',
        },
      },
    ],
    conclusion: 'Byzantine fault tolerance is possible but requires more nodes and communication rounds than crash fault tolerance.',
  },

  'clocks': {
    title: 'Logical Time and Causality',
    videoUrl: 'https://www.youtube.com/watch?v=x-D8iFU1d-o',
    videoId: 'x-D8iFU1d-o',
    overview: 'Physical clocks cannot perfectly synchronize across distributed systems. Logical clocks (Lamport and Vector clocks) capture causality - the "happens-before" relationship between events - without relying on synchronized time.',
    tags: ['clocks', 'causality', 'lamport', 'vector-clocks'],
    sections: [
      {
        title: 'Happens-Before Relation',
        content: 'Event A happens-before B if: A and B are on the same node with A first, A is a send and B its receive, or there\'s a chain of such relationships.',
        quotes: [
          'If A happens before B, then A might have caused B.',
          'Two events are concurrent if neither happens before the other.',
        ],
        timestamp: {
          time: '0:00',
          link: 'https://youtu.be/x-D8iFU1d-o?t=0',
          description: 'The happens-before relation',
        },
      },
      {
        title: 'Lamport Clocks',
        content: 'A simple counter: increment before send, set to max(local, received)+1 on receive. If A→B then L(A) < L(B), but L(A) < L(B) does not imply A→B.',
        quotes: [
          'Lamport timestamps give us a total order consistent with causality.',
        ],
        timestamp: {
          time: '8:00',
          link: 'https://youtu.be/x-D8iFU1d-o?t=480',
          description: 'Lamport clock algorithm',
        },
      },
      {
        title: 'Vector Clocks',
        content: 'Each node maintains a vector of counters (one per node). Vector clocks can detect concurrent events: A→B iff V(A) < V(B) component-wise.',
        quotes: [
          'Vector clocks capture the full causality relationship.',
          'Two events are concurrent if neither vector clock dominates the other.',
        ],
        timestamp: {
          time: '15:00',
          link: 'https://youtu.be/x-D8iFU1d-o?t=900',
          description: 'Vector clock algorithm',
        },
      },
    ],
    conclusion: 'Vector clocks fully capture causality, enabling detection of concurrent events. This is essential for conflict detection in replicated systems.',
  },

  'raft': {
    title: 'Raft Consensus Algorithm',
    videoUrl: 'https://www.youtube.com/watch?v=uXEYuDwm7e4',
    videoId: 'uXEYuDwm7e4',
    overview: 'Raft is a consensus algorithm designed for understandability. It provides total order broadcast through leader election and log replication, ensuring all nodes agree on the same sequence of commands.',
    tags: ['consensus', 'raft', 'leader-election', 'replication'],
    sections: [
      {
        title: 'Leader Election',
        content: 'Nodes start as followers. If no heartbeat is received, a node becomes a candidate and requests votes. A majority of votes makes it the leader for that term.',
        quotes: [
          'Every node can be in one of three states: follower, candidate, or leader.',
          'A higher term number always takes precedence.',
        ],
        timestamp: {
          time: '0:01',
          link: 'https://youtu.be/uXEYuDwm7e4?t=1',
          description: 'Leader election process',
        },
      },
      {
        title: 'Log Replication',
        content: 'The leader appends commands to its log and replicates to followers. Once a majority acknowledges, the entry is committed and can be applied.',
        quotes: [
          'The leader appends new entries to its log, then replicates them to followers.',
          'Entries are committed once a quorum acknowledges them.',
        ],
        timestamp: {
          time: '7:28',
          link: 'https://youtu.be/uXEYuDwm7e4?t=448',
          description: 'Log replication mechanism',
        },
      },
      {
        title: 'Safety Properties',
        content: 'Raft ensures: election safety (one leader per term), leader completeness (committed entries survive elections), and state machine safety (same commands in same order).',
        quotes: [
          'Followers grant votes only if the candidate\'s log is at least as up-to-date as theirs.',
        ],
        timestamp: {
          time: '18:00',
          link: 'https://youtu.be/uXEYuDwm7e4?t=1080',
          description: 'Safety guarantees',
        },
      },
    ],
    conclusion: 'Raft provides understandable consensus through clear separation of concerns: leader election, log replication, and commitment. It\'s widely used in production systems.',
  },

  'broadcast': {
    title: 'Broadcast Protocols',
    videoUrl: 'https://www.youtube.com/watch?v=A8oamrHf_cQ',
    videoId: 'A8oamrHf_cQ',
    overview: 'Broadcast protocols ensure messages are delivered to all nodes with various ordering guarantees: FIFO (per-sender order), Causal (respects causality), and Total Order (global order).',
    tags: ['broadcast', 'ordering', 'FIFO', 'causal', 'total-order'],
    sections: [
      {
        title: 'FIFO Broadcast',
        content: 'Messages from the same sender are delivered in the order they were sent. Messages from different senders may be delivered in any order.',
        quotes: [],
        timestamp: {
          time: '0:00',
          link: 'https://youtu.be/A8oamrHf_cQ?t=0',
          description: 'FIFO broadcast',
        },
      },
      {
        title: 'Causal Broadcast',
        content: 'If message A causally precedes message B, then A must be delivered before B at all nodes. Concurrent messages may be delivered in any order.',
        quotes: [],
        timestamp: {
          time: '10:00',
          link: 'https://youtu.be/A8oamrHf_cQ?t=600',
          description: 'Causal broadcast',
        },
      },
      {
        title: 'Total Order Broadcast',
        content: 'All nodes deliver all messages in exactly the same order. This is equivalent to consensus and can be used for state machine replication.',
        quotes: [],
        timestamp: {
          time: '20:00',
          link: 'https://youtu.be/A8oamrHf_cQ?t=1200',
          description: 'Total order broadcast',
        },
      },
    ],
    conclusion: 'Different broadcast orderings provide different consistency guarantees. Total order broadcast is the strongest and is equivalent to solving consensus.',
  },
};

// Get lecture content for a project
export function getLectureForProject(projectId: string): LectureContent | null {
  return lectureContent[projectId] || null;
}

// Extract YouTube video ID from URL
export function extractVideoId(url: string): string {
  const match = url.match(/(?:youtu\.be\/|youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=))([^&?]+)/);
  return match ? match[1] : '';
}

// Format timestamp for display
export function formatTimestamp(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}
