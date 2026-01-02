package simulation

import (
	"context"
	"encoding/json"
	"log"
	"sync"
	"time"

	"github.com/ersantana/distributed-systems-learning/packages/network/transport"
	"github.com/ersantana/distributed-systems-learning/packages/protocol"
	"github.com/ersantana/distributed-systems-learning/packages/simulation/engine"
)

// Broadcaster interface for sending messages to clients
type Broadcaster interface {
	BroadcastJSON(v interface{}) error
}

// ProjectSimulation interface that all project simulations must implement
type ProjectSimulation interface {
	Start(ctx context.Context) error
	Stop() error
	GetState() *protocol.SimulationStateResponse
	GetNodes() map[string]protocol.NodeState
	CrashNode(nodeID string) error
	RecoverNode(nodeID string) error
}

// Manager orchestrates all simulations
type Manager struct {
	mu sync.RWMutex

	broadcaster Broadcaster
	engine      *engine.Engine
	transport   *transport.NetworkTransport
	simulation  ProjectSimulation

	currentProject string
	currentScenario string
	ctx            context.Context
	cancel         context.CancelFunc

	timeline []protocol.TimelineEvent
}

// NewManager creates a new simulation manager
func NewManager(broadcaster Broadcaster) *Manager {
	return &Manager{
		broadcaster: broadcaster,
		timeline:    make([]protocol.TimelineEvent, 0),
	}
}

// eventEmitter implements engine.EventEmitter
type eventEmitter struct {
	manager *Manager
}

func (e *eventEmitter) Emit(eventType string, data map[string]interface{}) {
	e.manager.handleEvent(eventType, data)
}

// handleEvent processes events from the simulation engine
func (m *Manager) handleEvent(eventType string, data map[string]interface{}) {
	m.mu.Lock()
	event := protocol.TimelineEvent{
		Time: time.Now().UnixMilli(),
		Type: eventType,
		Data: data,
	}
	m.timeline = append(m.timeline, event)
	// Keep last 100 events
	if len(m.timeline) > 100 {
		m.timeline = m.timeline[1:]
	}
	m.mu.Unlock()

	// Broadcast event to clients
	msg := map[string]interface{}{
		"type": "timeline_event",
		"event": event,
	}
	if err := m.broadcaster.BroadcastJSON(msg); err != nil {
		log.Printf("Error broadcasting event: %v", err)
	}
}

// Start starts a simulation for the given project
func (m *Manager) Start(project, scenario string, config protocol.StartSimulationRequest) error {
	// Stop any existing simulation first (outside of lock to avoid deadlock)
	m.mu.Lock()
	if m.cancel != nil {
		m.cancel()
	}
	m.mu.Unlock()

	// Set up new simulation state
	m.mu.Lock()
	m.currentProject = project
	m.currentScenario = scenario
	m.timeline = make([]protocol.TimelineEvent, 0)
	m.ctx, m.cancel = context.WithCancel(context.Background())

	// Create transport
	m.transport = transport.NewNetworkTransport()
	m.mu.Unlock()

	// Set up drop handler to emit events
	m.transport.OnDrop(func(env *transport.Envelope, reason string) {
		m.handleEvent("message_dropped", map[string]interface{}{
			"from":   env.From,
			"to":     env.To,
			"type":   string(env.Type),
			"reason": reason,
		})
		// Also broadcast specific message dropped event
		msg := &protocol.MessageEventResponse{
			Type:        protocol.MsgMessageDropped,
			MessageID:   env.ID,
			From:        env.From,
			To:          env.To,
			MessageType: string(env.Type),
			Reason:      reason,
		}
		m.broadcaster.BroadcastJSON(msg)
	})

	// Create engine config
	engineConfig := engine.Config{
		Speed:       config.Config.Speed,
		TickRate:    100 * time.Millisecond,
		StepMode:    config.Config.StepMode,
		ProjectName: project,
		Scenario:    scenario,
	}
	if engineConfig.Speed == 0 {
		engineConfig.Speed = 1.0
	}

	// Create engine with event emitter
	m.engine = engine.NewEngine(&eventEmitter{manager: m}, engineConfig)

	// Create project-specific simulation
	var err error
	switch project {
	case "two-generals":
		m.simulation, err = m.createTwoGeneralsSimulation(scenario, config)
	case "clocks":
		m.simulation, err = m.createClocksSimulation(scenario, config)
	case "byzantine":
		m.simulation, err = m.createByzantineSimulation(scenario, config)
	default:
		// For projects not yet implemented, create a demo simulation
		m.simulation, err = m.createDemoSimulation(project, config)
	}

	if err != nil {
		return err
	}

	// Start the simulation
	if err := m.simulation.Start(m.ctx); err != nil {
		return err
	}

	// Broadcast initial state
	m.broadcastState()

	return nil
}

// Stop stops the current simulation
func (m *Manager) Stop() error {
	m.mu.Lock()
	defer m.mu.Unlock()

	if m.simulation != nil {
		m.simulation.Stop()
	}
	if m.cancel != nil {
		m.cancel()
	}
	if m.engine != nil {
		m.engine.Stop()
	}

	m.simulation = nil
	m.engine = nil
	m.currentProject = ""

	return nil
}

// Pause pauses the simulation
func (m *Manager) Pause() {
	m.mu.RLock()
	defer m.mu.RUnlock()

	if m.engine != nil {
		m.engine.Pause()
		m.broadcastState()
	}
}

// Resume resumes the simulation
func (m *Manager) Resume() {
	m.mu.RLock()
	defer m.mu.RUnlock()

	if m.engine != nil {
		m.engine.Resume()
		m.broadcastState()
	}
}

// Step advances the simulation by one step
func (m *Manager) Step() {
	m.mu.RLock()
	defer m.mu.RUnlock()

	if m.engine != nil {
		m.engine.Step()
		// Give time for tick to process
		time.Sleep(50 * time.Millisecond)
		m.broadcastState()
	}
}

// SetSpeed sets the simulation speed
func (m *Manager) SetSpeed(speed float64) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	if m.engine != nil {
		m.engine.SetSpeed(speed)
	}
}

// CrashNode crashes a node
func (m *Manager) CrashNode(nodeID string) error {
	m.mu.RLock()
	defer m.mu.RUnlock()

	if m.simulation != nil {
		err := m.simulation.CrashNode(nodeID)
		if err == nil {
			m.handleEvent("node_crashed", map[string]interface{}{
				"nodeId": nodeID,
			})
			m.broadcastState()
		}
		return err
	}
	return nil
}

// RecoverNode recovers a crashed node
func (m *Manager) RecoverNode(nodeID string) error {
	m.mu.RLock()
	defer m.mu.RUnlock()

	if m.simulation != nil {
		err := m.simulation.RecoverNode(nodeID)
		if err == nil {
			m.handleEvent("node_recovered", map[string]interface{}{
				"nodeId": nodeID,
			})
			m.broadcastState()
		}
		return err
	}
	return nil
}

// InjectPartition creates a network partition
func (m *Manager) InjectPartition(from, to string, bidirectional bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	if m.transport != nil {
		if bidirectional {
			m.transport.CreateBidirectionalPartition(from, to)
		} else {
			m.transport.SetPartition(from, to, true)
		}
		m.handleEvent("partition_created", map[string]interface{}{
			"from":          from,
			"to":            to,
			"bidirectional": bidirectional,
		})
		m.broadcastState()
	}
}

// HealPartition heals a network partition
func (m *Manager) HealPartition(from, to string, bidirectional bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	if m.transport != nil {
		if bidirectional {
			m.transport.ClearBidirectionalPartition(from, to)
		} else {
			m.transport.ClearPartition(from, to)
		}
		m.handleEvent("partition_healed", map[string]interface{}{
			"from":          from,
			"to":            to,
			"bidirectional": bidirectional,
		})
		m.broadcastState()
	}
}

// GetState returns the current simulation state
func (m *Manager) GetState() *protocol.SimulationStateResponse {
	m.mu.RLock()
	defer m.mu.RUnlock()

	if m.simulation != nil {
		state := m.simulation.GetState()
		state.Timeline = m.timeline
		return state
	}

	// Return empty state
	return &protocol.SimulationStateResponse{
		Type:        protocol.MsgSimulationState,
		VirtualTime: time.Now().UnixMilli(),
		Mode:        "paused",
		Speed:       1.0,
		Running:     false,
		Nodes:       make(map[string]protocol.NodeState),
	}
}

// broadcastState sends current state to all clients
func (m *Manager) broadcastState() {
	if m.simulation != nil {
		state := m.simulation.GetState()
		state.Timeline = m.timeline
		m.broadcaster.BroadcastJSON(state)
	}
}

// BroadcastMessage sends a specific message to clients
func (m *Manager) BroadcastMessage(msg interface{}) {
	if err := m.broadcaster.BroadcastJSON(msg); err != nil {
		log.Printf("Error broadcasting message: %v", err)
	}
}

// GetEngine returns the simulation engine
func (m *Manager) GetEngine() *engine.Engine {
	return m.engine
}

// GetTransport returns the network transport
func (m *Manager) GetTransport() *transport.NetworkTransport {
	return m.transport
}

// IsRunning returns whether a simulation is running
func (m *Manager) IsRunning() bool {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.engine != nil && m.engine.IsRunning()
}

// Helper to marshal interface to JSON bytes
func toJSON(v interface{}) []byte {
	data, _ := json.Marshal(v)
	return data
}
