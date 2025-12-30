import { useCallback } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  BackgroundVariant,
} from '@xyflow/react';
import type { Node, Edge, NodeProps } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useSimulationStore } from '../../stores/simulationStore';

interface NodeVisualizerProps {
  onNodeClick?: (nodeId: string) => void;
  onCrashNode?: (nodeId: string) => void;
  onRecoverNode?: (nodeId: string) => void;
}

interface DistributedNodeData {
  label: string;
  status: string;
  role?: string;
  term?: number;
  [key: string]: unknown;
}

// Custom node component with dark theme
function DistributedNode({ data }: NodeProps<Node<DistributedNodeData>>) {
  const nodeData = data as DistributedNodeData;

  const statusStyles: Record<string, { border: string; bg: string; glow: string }> = {
    running: {
      border: '#10b981',
      bg: 'rgba(16, 185, 129, 0.1)',
      glow: '0 0 20px rgba(16, 185, 129, 0.3)',
    },
    crashed: {
      border: '#ef4444',
      bg: 'rgba(239, 68, 68, 0.15)',
      glow: '0 0 20px rgba(239, 68, 68, 0.3)',
    },
    partitioned: {
      border: '#f59e0b',
      bg: 'rgba(245, 158, 11, 0.1)',
      glow: '0 0 20px rgba(245, 158, 11, 0.3)',
    },
    byzantine: {
      border: '#8b5cf6',
      bg: 'rgba(139, 92, 246, 0.1)',
      glow: '0 0 20px rgba(139, 92, 246, 0.3)',
    },
  };

  const style = statusStyles[nodeData.status] || {
    border: '#6b7280',
    bg: 'rgba(107, 114, 128, 0.1)',
    glow: 'none',
  };

  const roleLabel = nodeData.role ? ` (${nodeData.role})` : '';

  return (
    <div
      className="distributed-node"
      style={{
        border: `2px solid ${style.border}`,
        borderRadius: '50%',
        width: 90,
        height: 90,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: style.bg,
        cursor: 'pointer',
        boxShadow: style.glow,
        transition: 'all 0.2s ease',
      }}
    >
      <Handle
        type="target"
        position={Position.Top}
        style={{
          background: style.border,
          border: 'none',
          width: 8,
          height: 8,
        }}
      />
      <div style={{
        fontWeight: 600,
        fontSize: 14,
        color: '#f4f4f5',
        letterSpacing: '-0.01em',
      }}>
        {nodeData.label}
      </div>
      <div style={{
        fontSize: 10,
        color: '#a1a1aa',
        marginTop: 2,
      }}>
        {nodeData.status}
        {roleLabel}
      </div>
      {nodeData.term !== undefined && (
        <div style={{
          fontSize: 9,
          color: '#71717a',
          marginTop: 1,
        }}>
          Term: {nodeData.term}
        </div>
      )}
      <Handle
        type="source"
        position={Position.Bottom}
        style={{
          background: style.border,
          border: 'none',
          width: 8,
          height: 8,
        }}
      />
    </div>
  );
}

const nodeTypes = {
  distributed: DistributedNode,
};

export function NodeVisualizer({
  onNodeClick,
  onCrashNode,
  onRecoverNode,
}: NodeVisualizerProps) {
  const { nodes, partitions, selectedNode, setSelectedNode } = useSimulationStore();

  // Convert nodes to React Flow nodes
  const flowNodes: Node<DistributedNodeData>[] = Object.entries(nodes).map(([id, node], index) => {
    const angle = (2 * Math.PI * index) / Object.keys(nodes).length - Math.PI / 2;
    const radius = 160;
    const x = 280 + radius * Math.cos(angle);
    const y = 200 + radius * Math.sin(angle);

    return {
      id,
      type: 'distributed',
      position: { x, y },
      data: {
        label: id,
        status: node.status,
        role: node.role,
        term: node.term,
      },
      selected: id === selectedNode,
    };
  });

  // Create edges based on cluster topology (fully connected for now)
  const flowEdges: Edge[] = [];
  const nodeIds = Object.keys(nodes);

  for (let i = 0; i < nodeIds.length; i++) {
    for (let j = i + 1; j < nodeIds.length; j++) {
      const from = nodeIds[i];
      const to = nodeIds[j];

      // Check if partitioned
      const isPartitioned = partitions.some(
        (p) =>
          (p.from === from && p.to === to) ||
          (p.from === to && p.to === from)
      );

      flowEdges.push({
        id: `${from}-${to}`,
        source: from,
        target: to,
        style: {
          stroke: isPartitioned ? '#ef4444' : 'rgba(148, 163, 184, 0.3)',
          strokeWidth: isPartitioned ? 2 : 1,
          strokeDasharray: isPartitioned ? '5,5' : undefined,
        },
        animated: !isPartitioned,
      });
    }
  }

  const handleNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      setSelectedNode(node.id);
      onNodeClick?.(node.id);
    },
    [onNodeClick, setSelectedNode]
  );

  return (
    <div style={{ width: '100%', height: '420px' }}>
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        fitView
        attributionPosition="bottom-left"
        proOptions={{ hideAttribution: true }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={20}
          size={1}
          color="rgba(255, 255, 255, 0.05)"
        />
        <Controls
          showInteractive={false}
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
          }}
        />
      </ReactFlow>

      {selectedNode && nodes[selectedNode] && (
        <div className="node-details">
          <h4>Node: {selectedNode}</h4>
          <p><strong>Status:</strong> {nodes[selectedNode].status}</p>
          {nodes[selectedNode].role && <p><strong>Role:</strong> {nodes[selectedNode].role}</p>}
          {nodes[selectedNode].term !== undefined && (
            <p><strong>Term:</strong> {nodes[selectedNode].term}</p>
          )}
          <div className="node-actions">
            {nodes[selectedNode].status === 'crashed' ? (
              <button
                className="recover"
                onClick={() => onRecoverNode?.(selectedNode)}
              >
                Recover Node
              </button>
            ) : (
              <button
                className="crash"
                onClick={() => onCrashNode?.(selectedNode)}
              >
                Crash Node
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
