package clocks

import (
	"context"
	"fmt"
	"math/rand"
	"sync"
	"time"

	"github.com/ersantana/distributed-systems-learning/packages/core/clock"
	"github.com/ersantana/distributed-systems-learning/packages/network/transport"
	"github.com/ersantana/distributed-systems-learning/packages/protocol"
	"github.com/ersantana/distributed-systems-learning/packages/simulation/engine"
)

const (
	MsgEvent   transport.MessageType = "event"
	MsgRequest transport.MessageType = "request"
	MsgReply   transport.MessageType = "reply"
)

// Simulation implements the Logical Clocks visualization
type Simulation struct {
	mu sync.RWMutex

	engine    *engine.Engine
	transport *transport.NetworkTransport
	broadcast func(interface{})

	nodes       []*ClockNode
	nodeCount   int
	events      []CausalEvent
	scenario    string

	running bool
	ctx     context.Context
	cancel  context.CancelFunc
}

// CausalEvent represents an event in the space-time diagram
type CausalEvent struct {
	ID          string            `json:"id"`
	NodeID      string            `json:"nodeId"`
	Type        string            `json:"type"` // "local", "send", "receive"
	Time        int64             `json:"time"`
	LamportTime uint64            `json:"lamportTime"`
	VectorClock map[string]uint64 `json:"vectorClock"`
	RelatedTo   string            `json:"relatedTo,omitempty"` // ID of related event (for send/receive pairs)
}

// ClockNode represents a node with logical clocks
type ClockNode struct {
	mu sync.RWMutex

	id           string
	status       string
	lamportClock *clock.LamportClock
	vectorClock  *clock.VectorClock
	eventCount   int

	inbox      chan *transport.Envelope
	simulation *Simulation
	nodeIDs    []string
}

// LamportClock wrapper with Send/Receive semantics
func (n *ClockNode) lamportSend() uint64 {
	return n.lamportClock.Increment()
}

func (n *ClockNode) lamportReceive(received uint64) uint64 {
	return n.lamportClock.Update(received)
}

// Config for Clocks simulation
type Config struct {
	NodeCount int
	Scenario  string
}

// NewSimulation creates a new Clocks simulation
func NewSimulation(eng *engine.Engine, trans *transport.NetworkTransport, broadcast func(interface{}), config Config) *Simulation {
	if config.NodeCount == 0 {
		config.NodeCount = 3
	}

	sim := &Simulation{
		engine:    eng,
		transport: trans,
		broadcast: broadcast,
		nodeCount: config.NodeCount,
		scenario:  config.Scenario,
		events:    make([]CausalEvent, 0),
	}

	// Set up network with some latency but no drops
	trans.SetLatency(50*time.Millisecond, 150*time.Millisecond)
	trans.SetPacketLoss(0)

	// Create node IDs first
	nodeIDs := make([]string, config.NodeCount)
	for i := 0; i < config.NodeCount; i++ {
		nodeIDs[i] = fmt.Sprintf("node-%d", i+1)
	}

	// Create nodes
	sim.nodes = make([]*ClockNode, config.NodeCount)
	for i := 0; i < config.NodeCount; i++ {
		node := sim.newClockNode(nodeIDs[i], nodeIDs)
		sim.nodes[i] = node
		trans.RegisterHandler(nodeIDs[i], node.handleMessage)
		eng.AddNode(node)
	}

	return sim
}

func (s *Simulation) newClockNode(id string, nodeIDs []string) *ClockNode {
	return &ClockNode{
		id:           id,
		status:       "running",
		lamportClock: clock.NewLamportClock(),
		vectorClock:  clock.NewVectorClock(id, nodeIDs),
		inbox:        make(chan *transport.Envelope, 100),
		simulation:   s,
		nodeIDs:      nodeIDs,
	}
}

// Start starts the simulation
func (s *Simulation) Start(ctx context.Context) error {
	s.mu.Lock()
	s.running = true
	s.ctx, s.cancel = context.WithCancel(ctx)
	s.mu.Unlock()

	return s.engine.Start(ctx)
}

// Stop stops the simulation
func (s *Simulation) Stop() error {
	s.mu.Lock()
	s.running = false
	if s.cancel != nil {
		s.cancel()
	}
	s.mu.Unlock()

	return s.engine.Stop()
}

// GetState returns the current simulation state
func (s *Simulation) GetState() *protocol.SimulationStateResponse {
	s.mu.RLock()
	defer s.mu.RUnlock()

	nodes := make(map[string]protocol.NodeState)

	for _, node := range s.nodes {
		nodeState := node.GetState()
		nodes[node.id] = protocol.NodeState{
			ID:     node.id,
			Status: node.status,
			Role:   "participant",
			Clock:  nodeState["vectorClock"].(map[string]uint64),
			CustomState: map[string]interface{}{
				"lamportTime": nodeState["lamportTime"],
				"eventCount":  nodeState["eventCount"],
			},
		}
	}

	mode := "step"
	if s.engine != nil {
		mode = s.engine.GetMode().String()
	}

	// Include events for timeline visualization
	eventData := make([]map[string]interface{}, len(s.events))
	for i, evt := range s.events {
		eventData[i] = map[string]interface{}{
			"id":          evt.ID,
			"nodeId":      evt.NodeID,
			"type":        evt.Type,
			"time":        evt.Time,
			"lamportTime": evt.LamportTime,
			"vectorClock": evt.VectorClock,
			"relatedTo":   evt.RelatedTo,
		}
	}

	return &protocol.SimulationStateResponse{
		Type:        protocol.MsgSimulationState,
		VirtualTime: time.Now().UnixMilli(),
		Mode:        mode,
		Speed:       1.0,
		Running:     s.running,
		Nodes:       nodes,
	}
}

// GetNodes returns node states
func (s *Simulation) GetNodes() map[string]protocol.NodeState {
	state := s.GetState()
	return state.Nodes
}

// CrashNode crashes a node
func (s *Simulation) CrashNode(nodeID string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	for _, node := range s.nodes {
		if node.id == nodeID {
			node.status = "crashed"
			return nil
		}
	}
	return fmt.Errorf("unknown node: %s", nodeID)
}

// RecoverNode recovers a crashed node
func (s *Simulation) RecoverNode(nodeID string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	for _, node := range s.nodes {
		if node.id == nodeID {
			node.status = "running"
			return nil
		}
	}
	return fmt.Errorf("unknown node: %s", nodeID)
}

// ClockNode implements engine.NodeController

func (n *ClockNode) ID() string {
	return n.id
}

func (n *ClockNode) Start(ctx context.Context) error {
	return nil
}

func (n *ClockNode) Stop() error {
	return nil
}

func (n *ClockNode) Tick() {
	n.mu.Lock()
	defer n.mu.Unlock()

	if n.status != "running" {
		return
	}

	// Process any pending messages
	select {
	case env := <-n.inbox:
		n.processMessage(env)
	default:
		// Randomly perform local events or send messages
		if rand.Float64() < 0.3 { // 30% chance per tick
			if rand.Float64() < 0.5 {
				n.performLocalEvent()
			} else {
				n.sendRandomMessage()
			}
		}
	}
}

func (n *ClockNode) GetState() map[string]interface{} {
	n.mu.RLock()
	defer n.mu.RUnlock()

	return map[string]interface{}{
		"id":          n.id,
		"status":      n.status,
		"lamportTime": n.lamportClock.Time(),
		"vectorClock": n.vectorClock.Time(),
		"eventCount":  n.eventCount,
	}
}

func (n *ClockNode) handleMessage(env *transport.Envelope) {
	n.inbox <- env
}

func (n *ClockNode) processMessage(env *transport.Envelope) {
	sim := n.simulation

	// Merge clocks on receive
	if env.VectorClock != nil {
		n.vectorClock.Merge(env.VectorClock)
	}
	if env.LamportTime > 0 {
		n.lamportReceive(env.LamportTime)
	}

	n.eventCount++

	// Record event
	eventID := fmt.Sprintf("%s-recv-%d", n.id, n.eventCount)
	event := CausalEvent{
		ID:          eventID,
		NodeID:      n.id,
		Type:        "receive",
		Time:        time.Now().UnixMilli(),
		LamportTime: n.lamportClock.Time(),
		VectorClock: n.vectorClock.Time(),
		RelatedTo:   env.ID,
	}

	sim.mu.Lock()
	sim.events = append(sim.events, event)
	sim.mu.Unlock()

	// Broadcast message received event
	sim.broadcast(&protocol.MessageEventResponse{
		Type:        protocol.MsgMessageReceived,
		MessageID:   env.ID,
		From:        env.From,
		To:          env.To,
		MessageType: string(env.Type),
		Clock:       n.vectorClock.Time(),
	})

	// Broadcast clock update
	sim.broadcast(map[string]interface{}{
		"type":        "clock_update",
		"nodeId":      n.id,
		"lamportTime": n.lamportClock.Time(),
		"vectorClock": n.vectorClock.Time(),
		"eventType":   "receive",
	})
}

func (n *ClockNode) performLocalEvent() {
	sim := n.simulation

	// Increment clocks for local event
	n.lamportClock.Increment()
	n.vectorClock.Increment()
	n.eventCount++

	// Record event
	eventID := fmt.Sprintf("%s-local-%d", n.id, n.eventCount)
	event := CausalEvent{
		ID:          eventID,
		NodeID:      n.id,
		Type:        "local",
		Time:        time.Now().UnixMilli(),
		LamportTime: n.lamportClock.Time(),
		VectorClock: n.vectorClock.Time(),
	}

	sim.mu.Lock()
	sim.events = append(sim.events, event)
	sim.mu.Unlock()

	// Broadcast clock update
	sim.broadcast(map[string]interface{}{
		"type":        "clock_update",
		"nodeId":      n.id,
		"lamportTime": n.lamportClock.Time(),
		"vectorClock": n.vectorClock.Time(),
		"eventType":   "local",
	})
}

func (n *ClockNode) sendRandomMessage() {
	sim := n.simulation

	// Pick random target
	var targetID string
	for {
		targetID = n.nodeIDs[rand.Intn(len(n.nodeIDs))]
		if targetID != n.id {
			break
		}
	}

	// Increment clocks before send
	lamportTime := n.lamportSend()
	vectorTime := n.vectorClock.Increment()
	n.eventCount++

	// Record send event
	eventID := fmt.Sprintf("%s-send-%d", n.id, n.eventCount)
	event := CausalEvent{
		ID:          eventID,
		NodeID:      n.id,
		Type:        "send",
		Time:        time.Now().UnixMilli(),
		LamportTime: lamportTime,
		VectorClock: vectorTime,
	}

	sim.mu.Lock()
	sim.events = append(sim.events, event)
	sim.mu.Unlock()

	// Create and send envelope
	env := transport.NewEnvelope(n.id, targetID, MsgEvent, map[string]interface{}{
		"eventId": eventID,
		"message": fmt.Sprintf("Message from %s", n.id),
	})
	env.LamportTime = lamportTime
	env.VectorClock = vectorTime

	// Broadcast send event
	sim.broadcast(&protocol.MessageEventResponse{
		Type:        protocol.MsgMessageSent,
		MessageID:   env.ID,
		From:        env.From,
		To:          env.To,
		MessageType: string(env.Type),
		Clock:       vectorTime,
	})

	// Broadcast clock update
	sim.broadcast(map[string]interface{}{
		"type":        "clock_update",
		"nodeId":      n.id,
		"lamportTime": lamportTime,
		"vectorClock": vectorTime,
		"eventType":   "send",
	})

	sim.transport.Send(sim.ctx, env)
}

// GetEvents returns all recorded causal events
func (s *Simulation) GetEvents() []CausalEvent {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return append([]CausalEvent{}, s.events...)
}

// CompareEvents compares two events for causality
func (s *Simulation) CompareEvents(eventA, eventB string) string {
	s.mu.RLock()
	defer s.mu.RUnlock()

	var evtA, evtB *CausalEvent
	for i := range s.events {
		if s.events[i].ID == eventA {
			evtA = &s.events[i]
		}
		if s.events[i].ID == eventB {
			evtB = &s.events[i]
		}
	}

	if evtA == nil || evtB == nil {
		return "unknown"
	}

	relation := clock.CompareVectorClocks(evtA.VectorClock, evtB.VectorClock)
	switch relation {
	case clock.HappensBefore:
		return "before"
	case clock.HappensAfter:
		return "after"
	case clock.Concurrent:
		return "concurrent"
	case clock.Equal:
		return "equal"
	default:
		return "unknown"
	}
}

func init() {
	rand.Seed(time.Now().UnixNano())
}
