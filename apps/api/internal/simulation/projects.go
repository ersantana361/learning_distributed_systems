package simulation

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/ersantana/distributed-systems-learning/apps/api/internal/projects/byzantine"
	"github.com/ersantana/distributed-systems-learning/apps/api/internal/projects/clocks"
	"github.com/ersantana/distributed-systems-learning/apps/api/internal/projects/twogenerals"
	"github.com/ersantana/distributed-systems-learning/packages/protocol"
	"github.com/ersantana/distributed-systems-learning/packages/simulation/engine"
)

// createTwoGeneralsSimulation creates a Two Generals Problem simulation
func (m *Manager) createTwoGeneralsSimulation(scenario string, config protocol.StartSimulationRequest) (ProjectSimulation, error) {
	dropRate := 0.3 // Default 30% drop rate
	if scenario == "high_loss" {
		dropRate = 0.5
	} else if scenario == "no_loss" {
		dropRate = 0.0
	}

	sim := twogenerals.NewSimulation(
		m.engine,
		m.transport,
		m.BroadcastMessage,
		twogenerals.Config{
			DropRate:  dropRate,
			Scenario:  scenario,
			MaxRounds: 10,
		},
	)

	return sim, nil
}

// createClocksSimulation creates a Logical Clocks simulation
func (m *Manager) createClocksSimulation(scenario string, config protocol.StartSimulationRequest) (ProjectSimulation, error) {
	nodeCount := config.Config.NodeCount
	if nodeCount == 0 {
		nodeCount = 3
	}

	sim := clocks.NewSimulation(
		m.engine,
		m.transport,
		m.BroadcastMessage,
		clocks.Config{
			NodeCount: nodeCount,
			Scenario:  scenario,
		},
	)

	return sim, nil
}

// createByzantineSimulation creates a Byzantine Generals simulation
func (m *Manager) createByzantineSimulation(scenario string, config protocol.StartSimulationRequest) (ProjectSimulation, error) {
	nodeCount := config.Config.NodeCount
	if nodeCount == 0 {
		nodeCount = 4 // Default for 3f+1 with f=1
	}

	// Calculate traitor count based on scenario
	traitorCount := 1
	if scenario == "3f_fail" {
		// 3 nodes, 1 traitor - should fail
		nodeCount = 3
		traitorCount = 1
	} else if scenario == "commander_traitor" {
		traitorCount = 1
	}

	sim := byzantine.NewSimulation(
		m.engine,
		m.transport,
		m.BroadcastMessage,
		byzantine.Config{
			NodeCount:    nodeCount,
			TraitorCount: traitorCount,
			Scenario:     scenario,
		},
	)

	return sim, nil
}

// createDemoSimulation creates a demo simulation for unimplemented projects
func (m *Manager) createDemoSimulation(project string, config protocol.StartSimulationRequest) (ProjectSimulation, error) {
	nodeCount := config.Config.NodeCount
	if nodeCount == 0 {
		nodeCount = 5
	}

	demo := &DemoSimulation{
		engine:    m.engine,
		transport: m.transport,
		broadcast: m.BroadcastMessage,
		project:   project,
		nodeCount: nodeCount,
		nodes:     make(map[string]*DemoNode),
	}

	// Create demo nodes
	for i := 0; i < nodeCount; i++ {
		nodeID := fmt.Sprintf("node-%d", i+1)
		node := &DemoNode{
			id:         nodeID,
			status:     "running",
			role:       "participant",
			simulation: demo,
		}
		demo.nodes[nodeID] = node
		m.engine.AddNode(node)
	}

	return demo, nil
}

// DemoSimulation is a placeholder simulation for unimplemented projects
type DemoSimulation struct {
	mu sync.RWMutex

	engine    *engine.Engine
	transport interface{}
	broadcast func(interface{})
	project   string
	nodeCount int
	nodes     map[string]*DemoNode

	running bool
	ctx     context.Context
	cancel  context.CancelFunc
}

// DemoNode is a placeholder node
type DemoNode struct {
	mu sync.RWMutex

	id         string
	status     string
	role       string
	simulation *DemoSimulation
}

func (d *DemoSimulation) Start(ctx context.Context) error {
	d.mu.Lock()
	d.running = true
	d.ctx, d.cancel = context.WithCancel(ctx)
	d.mu.Unlock()

	return d.engine.Start(ctx)
}

func (d *DemoSimulation) Stop() error {
	d.mu.Lock()
	d.running = false
	if d.cancel != nil {
		d.cancel()
	}
	d.mu.Unlock()

	return d.engine.Stop()
}

func (d *DemoSimulation) GetState() *protocol.SimulationStateResponse {
	d.mu.RLock()
	defer d.mu.RUnlock()

	nodes := make(map[string]protocol.NodeState)
	for id, node := range d.nodes {
		nodes[id] = protocol.NodeState{
			ID:     id,
			Status: node.status,
			Role:   node.role,
			CustomState: map[string]interface{}{
				"message": fmt.Sprintf("Project '%s' simulation coming soon!", d.project),
			},
		}
	}

	mode := "step"
	if d.engine != nil {
		mode = d.engine.GetMode().String()
	}

	return &protocol.SimulationStateResponse{
		Type:        protocol.MsgSimulationState,
		VirtualTime: time.Now().UnixMilli(),
		Mode:        mode,
		Speed:       1.0,
		Running:     d.running,
		Nodes:       nodes,
	}
}

func (d *DemoSimulation) GetNodes() map[string]protocol.NodeState {
	return d.GetState().Nodes
}

func (d *DemoSimulation) CrashNode(nodeID string) error {
	d.mu.Lock()
	defer d.mu.Unlock()

	if node, ok := d.nodes[nodeID]; ok {
		node.status = "crashed"
		return nil
	}
	return fmt.Errorf("unknown node: %s", nodeID)
}

func (d *DemoSimulation) RecoverNode(nodeID string) error {
	d.mu.Lock()
	defer d.mu.Unlock()

	if node, ok := d.nodes[nodeID]; ok {
		node.status = "running"
		return nil
	}
	return fmt.Errorf("unknown node: %s", nodeID)
}

// DemoNode implements engine.NodeController

func (n *DemoNode) ID() string {
	return n.id
}

func (n *DemoNode) Start(ctx context.Context) error {
	return nil
}

func (n *DemoNode) Stop() error {
	return nil
}

func (n *DemoNode) Tick() {
	// Demo nodes don't do anything
}

func (n *DemoNode) GetState() map[string]interface{} {
	n.mu.RLock()
	defer n.mu.RUnlock()

	return map[string]interface{}{
		"id":     n.id,
		"status": n.status,
		"role":   n.role,
	}
}
