package main

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/ersantana/distributed-systems-learning/apps/api/internal/handlers"
	"github.com/ersantana/distributed-systems-learning/apps/api/internal/simulation"
	"github.com/ersantana/distributed-systems-learning/packages/protocol"
)

// Global simulation manager
var simManager *simulation.Manager

func main() {
	// Create hub
	hub := handlers.NewHub()
	go hub.Run()

	// Create simulation manager
	simManager = simulation.NewManager(hub)

	// Set up message handler
	hub.SetMessageHandler(handleMessage(hub))

	// Create WebSocket handler
	wsHandler := handlers.NewWebSocketHandler(hub)

	// Set up routes
	mux := http.NewServeMux()

	// WebSocket endpoint
	mux.Handle("/ws", wsHandler)

	// Health check
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":  "healthy",
			"clients": hub.ClientCount(),
		})
	})

	// API info
	mux.HandleFunc("/api", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]interface{}{
			"name":    "Distributed Systems Learning API",
			"version": "1.0.0",
			"projects": []string{
				"two-generals",
				"byzantine",
				"clocks",
				"broadcast",
				"raft",
				"quorum",
				"state-machine",
				"two-phase-commit",
				"consistency",
				"crdt",
			},
		})
	})

	// CORS middleware
	handler := corsMiddleware(mux)

	// Get port from environment
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	// Create server
	server := &http.Server{
		Addr:         ":" + port,
		Handler:      handler,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// Start server in goroutine
	go func() {
		log.Printf("Starting server on port %s", port)
		log.Printf("WebSocket endpoint: ws://localhost:%s/ws", port)
		log.Printf("API endpoint: http://localhost:%s/api", port)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("Server error: %v", err)
		}
	}()

	// Wait for interrupt signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down server...")

	// Graceful shutdown
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	if err := server.Shutdown(ctx); err != nil {
		log.Fatalf("Server forced to shutdown: %v", err)
	}

	log.Println("Server stopped")
}

// handleMessage creates a message handler function
func handleMessage(hub *handlers.Hub) func(clientID string, msgType string, data []byte) {
	return func(clientID string, msgType string, data []byte) {
		log.Printf("Received message from %s: %s", clientID, msgType)

		switch protocol.MessageType(msgType) {
		case protocol.MsgStartSimulation:
			msg, err := protocol.ParseStartSimulation(data)
			if err != nil {
				sendError(hub, clientID, "parse_error", err.Error())
				return
			}
			log.Printf("Starting simulation: project=%s, scenario=%s", msg.Project, msg.Scenario)

			// Start the simulation using the manager
			if err := simManager.Start(msg.Project, msg.Scenario, *msg); err != nil {
				sendError(hub, clientID, "start_error", err.Error())
				return
			}

			// State is automatically broadcast by the manager

		case protocol.MsgPauseSimulation:
			log.Println("Pausing simulation")
			simManager.Pause()

		case protocol.MsgResumeSimulation:
			log.Println("Resuming simulation")
			simManager.Resume()

		case protocol.MsgStopSimulation:
			log.Println("Stopping simulation")
			simManager.Stop()
			// Send stopped state
			response := protocol.NewSimulationState(
				time.Now().UnixMilli(),
				"paused",
				1.0,
				false,
				make(map[string]protocol.NodeState),
			)
			sendResponse(hub, response)

		case protocol.MsgStepForward:
			log.Println("Stepping forward")
			simManager.Step()

		case protocol.MsgSetSpeed:
			msg, err := protocol.ParseSetSpeed(data)
			if err != nil {
				sendError(hub, clientID, "parse_error", err.Error())
				return
			}
			log.Printf("Setting speed: %f", msg.Speed)
			simManager.SetSpeed(msg.Speed)

		case protocol.MsgInjectCrash:
			msg, err := protocol.ParseInjectCrash(data)
			if err != nil {
				sendError(hub, clientID, "parse_error", err.Error())
				return
			}
			log.Printf("Crashing node: %s", msg.NodeID)
			if err := simManager.CrashNode(msg.NodeID); err != nil {
				sendError(hub, clientID, "crash_error", err.Error())
			}

		case protocol.MsgRecoverNode:
			var msg protocol.RecoverNodeRequest
			if err := json.Unmarshal(data, &msg); err != nil {
				sendError(hub, clientID, "parse_error", err.Error())
				return
			}
			log.Printf("Recovering node: %s", msg.NodeID)
			if err := simManager.RecoverNode(msg.NodeID); err != nil {
				sendError(hub, clientID, "recover_error", err.Error())
			}

		case protocol.MsgInjectPartition:
			var msg protocol.InjectPartitionRequest
			if err := json.Unmarshal(data, &msg); err != nil {
				sendError(hub, clientID, "parse_error", err.Error())
				return
			}
			log.Printf("Creating partition: %s -> %s", msg.From, msg.To)
			simManager.InjectPartition(msg.From, msg.To, msg.Bidirectional)

		case protocol.MsgHealPartition:
			var msg protocol.HealPartitionRequest
			if err := json.Unmarshal(data, &msg); err != nil {
				sendError(hub, clientID, "parse_error", err.Error())
				return
			}
			log.Printf("Healing partition: %s -> %s", msg.From, msg.To)
			simManager.HealPartition(msg.From, msg.To, msg.Bidirectional)

		case protocol.MsgGetState:
			log.Println("Getting state")
			state := simManager.GetState()
			log.Printf("Got state: running=%v, nodes=%d", state.Running, len(state.Nodes))
			sendResponse(hub, state)
			log.Println("State response sent")

		default:
			log.Printf("Unknown message type: %s", msgType)
			sendError(hub, clientID, "unknown_type", "Unknown message type: "+msgType)
		}
	}
}

func sendResponse(hub *handlers.Hub, v interface{}) {
	if err := hub.BroadcastJSON(v); err != nil {
		log.Printf("Error broadcasting response: %v", err)
	}
}

func sendError(hub *handlers.Hub, clientID, code, message string) {
	response := protocol.NewError(code, message)
	data, _ := json.Marshal(response)
	hub.SendToClient(clientID, data)
}

func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")

		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}

		next.ServeHTTP(w, r)
	})
}
