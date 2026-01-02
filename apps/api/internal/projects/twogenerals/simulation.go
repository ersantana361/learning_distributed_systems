package twogenerals

import (
	"context"
	"fmt"
	"math/rand"
	"sync"
	"time"

	"github.com/ersantana/distributed-systems-learning/packages/network/transport"
	"github.com/ersantana/distributed-systems-learning/packages/protocol"
	"github.com/ersantana/distributed-systems-learning/packages/simulation/engine"
)

const (
	MsgPropose    transport.MessageType = "propose"
	MsgAck        transport.MessageType = "ack"
	MsgAckAck     transport.MessageType = "ack_ack"
	MsgDecision   transport.MessageType = "decision"
)

// Simulation implements the Two Generals Problem
type Simulation struct {
	mu sync.RWMutex

	engine    *engine.Engine
	transport *transport.NetworkTransport
	broadcast func(interface{})

	commander *GeneralNode
	responder *GeneralNode

	dropRate    float64
	scenario    string
	decision    string // "attack" or "retreat"
	round       int
	maxRounds   int

	running     bool
	ctx         context.Context
	cancel      context.CancelFunc
}

// GeneralNode represents a general in the problem
type GeneralNode struct {
	mu sync.RWMutex

	id            string
	role          string // "commander" or "responder"
	status        string // "running", "crashed"
	decision      string // "attack" or "retreat"
	confirmed     bool
	certaintyLevel int    // 0-100, how certain the general is

	messagesSent  int
	messagesAcked int
	awaitingAck   bool
	lastAckRound  int

	inbox         chan *transport.Envelope
	simulation    *Simulation
}

// Config for Two Generals simulation
type Config struct {
	DropRate  float64
	Scenario  string
	MaxRounds int
}

// NewSimulation creates a new Two Generals simulation
func NewSimulation(eng *engine.Engine, trans *transport.NetworkTransport, broadcast func(interface{}), config Config) *Simulation {
	if config.MaxRounds == 0 {
		config.MaxRounds = 10
	}
	if config.DropRate == 0 {
		config.DropRate = 0.3 // 30% default drop rate
	}

	sim := &Simulation{
		engine:    eng,
		transport: trans,
		broadcast: broadcast,
		dropRate:  config.DropRate,
		scenario:  config.Scenario,
		decision:  "attack",
		maxRounds: config.MaxRounds,
	}

	// Configure transport with drop rate
	trans.SetPacketLoss(config.DropRate)
	trans.SetLatency(50*time.Millisecond, 200*time.Millisecond)

	// Create nodes
	sim.commander = sim.newGeneralNode("general-1", "commander")
	sim.responder = sim.newGeneralNode("general-2", "responder")

	// Register handlers
	trans.RegisterHandler("general-1", sim.commander.handleMessage)
	trans.RegisterHandler("general-2", sim.responder.handleMessage)

	// Add nodes to engine
	eng.AddNode(sim.commander)
	eng.AddNode(sim.responder)

	return sim
}

func (s *Simulation) newGeneralNode(id, role string) *GeneralNode {
	return &GeneralNode{
		id:         id,
		role:       role,
		status:     "running",
		decision:   "",
		inbox:      make(chan *transport.Envelope, 100),
		simulation: s,
	}
}

// Start starts the simulation
func (s *Simulation) Start(ctx context.Context) error {
	s.mu.Lock()
	s.running = true
	s.ctx, s.cancel = context.WithCancel(ctx)
	s.mu.Unlock()

	// Commander initiates with attack proposal
	s.commander.decision = s.decision
	s.commander.awaitingAck = true

	// Start engine
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

	// Commander state
	cmdState := s.commander.GetState()
	nodes["general-1"] = protocol.NodeState{
		ID:     "general-1",
		Status: s.commander.status,
		Role:   "commander",
		CustomState: map[string]interface{}{
			"decision":       cmdState["decision"],
			"confirmed":      cmdState["confirmed"],
			"certaintyLevel": cmdState["certaintyLevel"],
			"messagesSent":   cmdState["messagesSent"],
			"messagesAcked":  cmdState["messagesAcked"],
			"awaitingAck":    cmdState["awaitingAck"],
		},
	}

	// Responder state
	respState := s.responder.GetState()
	nodes["general-2"] = protocol.NodeState{
		ID:     "general-2",
		Status: s.responder.status,
		Role:   "responder",
		CustomState: map[string]interface{}{
			"decision":       respState["decision"],
			"confirmed":      respState["confirmed"],
			"certaintyLevel": respState["certaintyLevel"],
			"messagesSent":   respState["messagesSent"],
			"messagesAcked":  respState["messagesAcked"],
		},
	}

	mode := "step"
	if s.engine != nil {
		mode = s.engine.GetMode().String()
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

	switch nodeID {
	case "general-1":
		s.commander.status = "crashed"
	case "general-2":
		s.responder.status = "crashed"
	default:
		return fmt.Errorf("unknown node: %s", nodeID)
	}
	return nil
}

// RecoverNode recovers a crashed node
func (s *Simulation) RecoverNode(nodeID string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	switch nodeID {
	case "general-1":
		s.commander.status = "running"
	case "general-2":
		s.responder.status = "running"
	default:
		return fmt.Errorf("unknown node: %s", nodeID)
	}
	return nil
}

// GeneralNode implements engine.NodeController

func (n *GeneralNode) ID() string {
	return n.id
}

func (n *GeneralNode) Start(ctx context.Context) error {
	return nil
}

func (n *GeneralNode) Stop() error {
	return nil
}

func (n *GeneralNode) Tick() {
	n.mu.Lock()
	defer n.mu.Unlock()

	if n.status != "running" {
		return
	}

	sim := n.simulation

	// Process any pending messages
	select {
	case env := <-n.inbox:
		n.processMessage(env)
	default:
		// No messages
	}

	// Commander logic: send proposal if awaiting ack
	if n.role == "commander" && n.awaitingAck && n.decision != "" {
		sim.mu.Lock()
		round := sim.round
		sim.round++
		sim.mu.Unlock()

		if round < sim.maxRounds {
			n.sendProposal()
		}
	}
}

func (n *GeneralNode) GetState() map[string]interface{} {
	n.mu.RLock()
	defer n.mu.RUnlock()

	return map[string]interface{}{
		"id":             n.id,
		"role":           n.role,
		"status":         n.status,
		"decision":       n.decision,
		"confirmed":      n.confirmed,
		"certaintyLevel": n.certaintyLevel,
		"messagesSent":   n.messagesSent,
		"messagesAcked":  n.messagesAcked,
		"awaitingAck":    n.awaitingAck,
	}
}

func (n *GeneralNode) handleMessage(env *transport.Envelope) {
	n.inbox <- env
}

func (n *GeneralNode) processMessage(env *transport.Envelope) {
	sim := n.simulation

	// Broadcast message received event
	sim.broadcast(&protocol.MessageEventResponse{
		Type:        protocol.MsgMessageReceived,
		MessageID:   env.ID,
		From:        env.From,
		To:          env.To,
		MessageType: string(env.Type),
		Payload:     env.Payload,
	})

	switch env.Type {
	case MsgPropose:
		// Responder receives attack proposal
		if n.role == "responder" {
			payload, ok := env.Payload.(map[string]interface{})
			if ok {
				if decision, exists := payload["decision"].(string); exists {
					n.decision = decision
					n.certaintyLevel = 50 // Received proposal but no confirmation
				}
			}
			// Send ACK
			n.sendAck(env.From)
		}

	case MsgAck:
		// Commander receives ACK
		if n.role == "commander" {
			n.messagesAcked++
			n.certaintyLevel = min(n.certaintyLevel+20, 80) // Can never be 100% certain
			// Send ACK-ACK
			n.sendAckAck(env.From)
		}

	case MsgAckAck:
		// Responder receives ACK-ACK
		if n.role == "responder" {
			n.messagesAcked++
			n.certaintyLevel = min(n.certaintyLevel+20, 80)
			n.confirmed = true
			// Could send another ACK, demonstrating infinite regress
		}
	}
}

func (n *GeneralNode) sendProposal() {
	sim := n.simulation
	targetID := "general-2"

	env := transport.NewEnvelope(n.id, targetID, MsgPropose, map[string]interface{}{
		"decision": n.decision,
		"round":    sim.round,
	})
	n.messagesSent++

	// Broadcast send event
	sim.broadcast(&protocol.MessageEventResponse{
		Type:        protocol.MsgMessageSent,
		MessageID:   env.ID,
		From:        env.From,
		To:          env.To,
		MessageType: string(env.Type),
		Payload:     env.Payload,
	})

	sim.transport.Send(sim.ctx, env)
}

func (n *GeneralNode) sendAck(to string) {
	sim := n.simulation

	env := transport.NewEnvelope(n.id, to, MsgAck, map[string]interface{}{
		"decision": n.decision,
		"ack":      true,
	})
	n.messagesSent++

	sim.broadcast(&protocol.MessageEventResponse{
		Type:        protocol.MsgMessageSent,
		MessageID:   env.ID,
		From:        env.From,
		To:          env.To,
		MessageType: string(env.Type),
	})

	sim.transport.Send(sim.ctx, env)
}

func (n *GeneralNode) sendAckAck(to string) {
	sim := n.simulation

	env := transport.NewEnvelope(n.id, to, MsgAckAck, map[string]interface{}{
		"ackAck": true,
	})
	n.messagesSent++

	sim.broadcast(&protocol.MessageEventResponse{
		Type:        protocol.MsgMessageSent,
		MessageID:   env.ID,
		From:        env.From,
		To:          env.To,
		MessageType: string(env.Type),
	})

	sim.transport.Send(sim.ctx, env)
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// SetDropRate allows changing the drop rate dynamically
func (s *Simulation) SetDropRate(rate float64) {
	s.mu.Lock()
	s.dropRate = rate
	s.mu.Unlock()
	s.transport.SetPacketLoss(rate)
}

// GetDropRate returns current drop rate
func (s *Simulation) GetDropRate() float64 {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.dropRate
}

func init() {
	rand.Seed(time.Now().UnixNano())
}
