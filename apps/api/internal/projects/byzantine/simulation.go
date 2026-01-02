package byzantine

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
	MsgVote      transport.MessageType = "vote"
	MsgRelay     transport.MessageType = "relay"
	MsgDecision  transport.MessageType = "decision"
)

// Behavior defines node behavior type
type Behavior int

const (
	BehaviorHonest Behavior = iota
	BehaviorTraitor
	BehaviorSilent
)

func (b Behavior) String() string {
	switch b {
	case BehaviorHonest:
		return "honest"
	case BehaviorTraitor:
		return "traitor"
	case BehaviorSilent:
		return "silent"
	default:
		return "unknown"
	}
}

// Simulation implements the Byzantine Generals Problem
type Simulation struct {
	mu sync.RWMutex

	engine    *engine.Engine
	transport *transport.NetworkTransport
	broadcast func(interface{})

	nodes       []*ByzantineNode
	nodeCount   int
	traitorCount int
	scenario    string
	round       int
	maxRounds   int
	commanderID string

	consensusReached bool
	finalDecision    string

	running bool
	ctx     context.Context
	cancel  context.CancelFunc
}

// ByzantineNode represents a general in the Byzantine problem
type ByzantineNode struct {
	mu sync.RWMutex

	id          string
	status      string
	behavior    Behavior
	isCommander bool
	decision    string // The value this node decides on

	receivedVotes map[string]map[string]string // round -> nodeID -> vote
	sentVotes     map[string]bool              // nodeID -> sent
	round         int

	inbox      chan *transport.Envelope
	simulation *Simulation
	nodeIDs    []string
}

// Config for Byzantine simulation
type Config struct {
	NodeCount    int
	TraitorCount int
	Scenario     string
}

// NewSimulation creates a new Byzantine Generals simulation
func NewSimulation(eng *engine.Engine, trans *transport.NetworkTransport, broadcast func(interface{}), config Config) *Simulation {
	if config.NodeCount == 0 {
		config.NodeCount = 4
	}
	if config.TraitorCount == 0 {
		// Default: demonstrate 3f+1 requirement
		config.TraitorCount = 1
	}

	sim := &Simulation{
		engine:       eng,
		transport:    trans,
		broadcast:    broadcast,
		nodeCount:    config.NodeCount,
		traitorCount: config.TraitorCount,
		scenario:     config.Scenario,
		maxRounds:    config.TraitorCount + 1, // OM(m) needs m+1 rounds
	}

	// Set up network - no drops, some latency
	trans.SetLatency(30*time.Millisecond, 100*time.Millisecond)
	trans.SetPacketLoss(0)

	// Create node IDs
	nodeIDs := make([]string, config.NodeCount)
	for i := 0; i < config.NodeCount; i++ {
		nodeIDs[i] = fmt.Sprintf("general-%d", i+1)
	}

	// Randomly select traitors (but not the commander in default scenario)
	traitorSet := make(map[int]bool)
	for len(traitorSet) < config.TraitorCount {
		idx := rand.Intn(config.NodeCount)
		// In default scenario, don't make commander (index 0) a traitor
		if config.Scenario != "commander_traitor" && idx == 0 {
			continue
		}
		traitorSet[idx] = true
	}

	// For commander_traitor scenario, make commander a traitor
	if config.Scenario == "commander_traitor" {
		traitorSet = map[int]bool{0: true}
	}

	// Create nodes
	sim.nodes = make([]*ByzantineNode, config.NodeCount)
	sim.commanderID = nodeIDs[0]

	for i := 0; i < config.NodeCount; i++ {
		behavior := BehaviorHonest
		if traitorSet[i] {
			behavior = BehaviorTraitor
		}

		node := sim.newByzantineNode(nodeIDs[i], nodeIDs, i == 0, behavior)
		sim.nodes[i] = node
		trans.RegisterHandler(nodeIDs[i], node.handleMessage)
		eng.AddNode(node)
	}

	return sim
}

func (s *Simulation) newByzantineNode(id string, nodeIDs []string, isCommander bool, behavior Behavior) *ByzantineNode {
	return &ByzantineNode{
		id:            id,
		status:        "running",
		behavior:      behavior,
		isCommander:   isCommander,
		receivedVotes: make(map[string]map[string]string),
		sentVotes:     make(map[string]bool),
		inbox:         make(chan *transport.Envelope, 100),
		simulation:    s,
		nodeIDs:       nodeIDs,
	}
}

// Start starts the simulation
func (s *Simulation) Start(ctx context.Context) error {
	s.mu.Lock()
	s.running = true
	s.ctx, s.cancel = context.WithCancel(ctx)

	// Commander initiates with "attack" decision
	if len(s.nodes) > 0 {
		commander := s.nodes[0]
		commander.decision = "attack"
	}
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
		status := node.status
		if node.behavior == BehaviorTraitor {
			status = "byzantine" // Special status for UI styling
		}

		nodes[node.id] = protocol.NodeState{
			ID:     node.id,
			Status: status,
			Role:   nodeState["role"].(string),
			CustomState: map[string]interface{}{
				"behavior":      node.behavior.String(),
				"decision":      nodeState["decision"],
				"isCommander":   nodeState["isCommander"],
				"round":         nodeState["round"],
				"votesReceived": nodeState["votesReceived"],
			},
		}
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

// ByzantineNode implements engine.NodeController

func (n *ByzantineNode) ID() string {
	return n.id
}

func (n *ByzantineNode) Start(ctx context.Context) error {
	return nil
}

func (n *ByzantineNode) Stop() error {
	return nil
}

func (n *ByzantineNode) Tick() {
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
	}

	// Commander sends initial vote in round 0
	if n.isCommander && n.round == 0 && !n.sentVotes["round0"] {
		n.sendInitialVotes()
		n.round = 1
		n.sentVotes["round0"] = true
	}

	// Check if we can make a decision
	n.tryDecide()
}

func (n *ByzantineNode) GetState() map[string]interface{} {
	n.mu.RLock()
	defer n.mu.RUnlock()

	role := "lieutenant"
	if n.isCommander {
		role = "commander"
	}

	votesReceived := 0
	for _, votes := range n.receivedVotes {
		votesReceived += len(votes)
	}

	return map[string]interface{}{
		"id":            n.id,
		"status":        n.status,
		"behavior":      n.behavior.String(),
		"role":          role,
		"decision":      n.decision,
		"isCommander":   n.isCommander,
		"round":         n.round,
		"votesReceived": votesReceived,
	}
}

func (n *ByzantineNode) handleMessage(env *transport.Envelope) {
	n.inbox <- env
}

func (n *ByzantineNode) processMessage(env *transport.Envelope) {
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
	case MsgVote:
		payload, ok := env.Payload.(map[string]interface{})
		if !ok {
			return
		}

		vote, _ := payload["vote"].(string)
		round, _ := payload["round"].(float64)
		roundKey := fmt.Sprintf("round%d", int(round))

		// Store the vote
		if n.receivedVotes[roundKey] == nil {
			n.receivedVotes[roundKey] = make(map[string]string)
		}
		n.receivedVotes[roundKey][env.From] = vote

		// Broadcast vote received event
		sim.broadcast(map[string]interface{}{
			"type":    "byzantine_vote",
			"from":    env.From,
			"to":      n.id,
			"vote":    vote,
			"round":   int(round),
		})

		// If not commander and haven't relayed yet, relay to others
		if !n.isCommander && !n.sentVotes[roundKey+"_relay"] {
			n.relayVote(vote, int(round))
			n.sentVotes[roundKey+"_relay"] = true
		}
	}
}

func (n *ByzantineNode) sendInitialVotes() {
	sim := n.simulation

	for _, targetID := range n.nodeIDs {
		if targetID == n.id {
			continue
		}

		vote := n.decision

		// Traitor sends conflicting votes
		if n.behavior == BehaviorTraitor {
			// Send different values to different generals
			if rand.Float64() < 0.5 {
				vote = "attack"
			} else {
				vote = "retreat"
			}

			// Broadcast conflict detected
			sim.broadcast(map[string]interface{}{
				"type":     "conflict_detected",
				"from":     n.id,
				"to":       targetID,
				"trueVote": n.decision,
				"sentVote": vote,
			})
		}

		if n.behavior == BehaviorSilent {
			continue // Silent nodes don't send
		}

		env := transport.NewEnvelope(n.id, targetID, MsgVote, map[string]interface{}{
			"vote":  vote,
			"round": 0,
		})

		sim.broadcast(&protocol.MessageEventResponse{
			Type:        protocol.MsgMessageSent,
			MessageID:   env.ID,
			From:        env.From,
			To:          env.To,
			MessageType: string(env.Type),
		})

		sim.transport.Send(sim.ctx, env)
	}
}

func (n *ByzantineNode) relayVote(vote string, round int) {
	sim := n.simulation

	// If traitor, may alter the vote when relaying
	if n.behavior == BehaviorTraitor {
		if rand.Float64() < 0.5 {
			if vote == "attack" {
				vote = "retreat"
			} else {
				vote = "attack"
			}
		}
	}

	if n.behavior == BehaviorSilent {
		return
	}

	for _, targetID := range n.nodeIDs {
		if targetID == n.id {
			continue
		}

		env := transport.NewEnvelope(n.id, targetID, MsgVote, map[string]interface{}{
			"vote":     vote,
			"round":    round + 1,
			"relayedFrom": n.id,
		})

		sim.broadcast(&protocol.MessageEventResponse{
			Type:        protocol.MsgMessageSent,
			MessageID:   env.ID,
			From:        env.From,
			To:          env.To,
			MessageType: string(env.Type),
		})

		sim.transport.Send(sim.ctx, env)
	}
}

func (n *ByzantineNode) tryDecide() {
	sim := n.simulation

	// Need votes from majority
	votesNeeded := (len(n.nodeIDs) / 2) + 1

	// Count votes from round 0
	round0Votes := n.receivedVotes["round0"]
	if len(round0Votes) < votesNeeded-1 { // -1 because we don't count self
		return
	}

	// Majority vote
	attackCount := 0
	retreatCount := 0

	for _, vote := range round0Votes {
		if vote == "attack" {
			attackCount++
		} else {
			retreatCount++
		}
	}

	// Make decision based on majority
	if attackCount >= retreatCount {
		n.decision = "attack"
	} else {
		n.decision = "retreat"
	}

	// Check if consensus is reached across honest nodes
	sim.mu.Lock()
	if !sim.consensusReached {
		allHonestAgree := true
		var honestDecision string

		for _, node := range sim.nodes {
			if node.behavior == BehaviorHonest && node.decision != "" {
				if honestDecision == "" {
					honestDecision = node.decision
				} else if node.decision != honestDecision {
					allHonestAgree = false
					break
				}
			}
		}

		if allHonestAgree && honestDecision != "" {
			sim.consensusReached = true
			sim.finalDecision = honestDecision

			sim.broadcast(map[string]interface{}{
				"type":     "consensus_reached",
				"decision": honestDecision,
				"honest":   allHonestAgree,
			})
		}
	}
	sim.mu.Unlock()
}

// Helper methods

// GetTraitorCount returns number of traitors
func (s *Simulation) GetTraitorCount() int {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.traitorCount
}

// IsConsensusReached returns whether consensus was reached
func (s *Simulation) IsConsensusReached() bool {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.consensusReached
}

// GetFinalDecision returns the final decision if consensus reached
func (s *Simulation) GetFinalDecision() string {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.finalDecision
}

func init() {
	rand.Seed(time.Now().UnixNano())
}
