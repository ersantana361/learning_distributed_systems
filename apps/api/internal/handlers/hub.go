package handlers

import (
	"encoding/json"
	"log"
	"sync"

	"github.com/gorilla/websocket"
)

// Client represents a WebSocket client
type Client struct {
	hub  *Hub
	conn *websocket.Conn
	send chan []byte
	id   string
}

// Hub manages WebSocket connections and broadcasts
type Hub struct {
	mu         sync.RWMutex
	clients    map[*Client]bool
	broadcast  chan []byte
	register   chan *Client
	unregister chan *Client

	// Simulation manager callback
	onMessage func(clientID string, msgType string, data []byte)
}

// NewHub creates a new WebSocket hub
func NewHub() *Hub {
	return &Hub{
		clients:    make(map[*Client]bool),
		broadcast:  make(chan []byte, 256),
		register:   make(chan *Client),
		unregister: make(chan *Client),
	}
}

// SetMessageHandler sets the message handler callback
func (h *Hub) SetMessageHandler(handler func(clientID string, msgType string, data []byte)) {
	h.onMessage = handler
}

// Run starts the hub's main loop
func (h *Hub) Run() {
	for {
		select {
		case client := <-h.register:
			h.mu.Lock()
			h.clients[client] = true
			h.mu.Unlock()
			log.Printf("Client connected: %s", client.id)

		case client := <-h.unregister:
			h.mu.Lock()
			if _, ok := h.clients[client]; ok {
				delete(h.clients, client)
				close(client.send)
			}
			h.mu.Unlock()
			log.Printf("Client disconnected: %s", client.id)

		case message := <-h.broadcast:
			h.mu.RLock()
			for client := range h.clients {
				select {
				case client.send <- message:
				default:
					h.mu.RUnlock()
					h.mu.Lock()
					close(client.send)
					delete(h.clients, client)
					h.mu.Unlock()
					h.mu.RLock()
				}
			}
			h.mu.RUnlock()
		}
	}
}

// Broadcast sends a message to all clients
func (h *Hub) Broadcast(message []byte) {
	log.Printf("[Broadcast] Sending to %d clients: %s", len(h.clients), string(message)[:min(len(message), 100)])
	h.broadcast <- message
}

// BroadcastJSON broadcasts a JSON message to all clients
func (h *Hub) BroadcastJSON(v interface{}) error {
	data, err := json.Marshal(v)
	if err != nil {
		log.Printf("[BroadcastJSON] Marshal error: %v", err)
		return err
	}
	log.Printf("[BroadcastJSON] Broadcasting: %s", string(data)[:min(len(data), 100)])
	h.Broadcast(data)
	return nil
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// SendToClient sends a message to a specific client
func (h *Hub) SendToClient(clientID string, message []byte) {
	h.mu.RLock()
	defer h.mu.RUnlock()

	for client := range h.clients {
		if client.id == clientID {
			select {
			case client.send <- message:
			default:
				// Client buffer full
			}
			return
		}
	}
}

// ClientCount returns the number of connected clients
func (h *Hub) ClientCount() int {
	h.mu.RLock()
	defer h.mu.RUnlock()
	return len(h.clients)
}

// readPump pumps messages from the websocket connection to the hub
func (c *Client) readPump() {
	defer func() {
		c.hub.unregister <- c
		c.conn.Close()
	}()

	for {
		_, message, err := c.conn.ReadMessage()
		if err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				log.Printf("error: %v", err)
			}
			log.Printf("[readPump] Connection closed for client %s: %v", c.id, err)
			break
		}

		log.Printf("[readPump] Raw message from %s: %s", c.id, string(message))

		// Parse message type
		var baseMsg struct {
			Type string `json:"type"`
		}
		if err := json.Unmarshal(message, &baseMsg); err != nil {
			log.Printf("[readPump] Error parsing message: %v", err)
			continue
		}

		log.Printf("[readPump] Parsed message type: %s", baseMsg.Type)

		// Call message handler
		if c.hub.onMessage != nil {
			c.hub.onMessage(c.id, baseMsg.Type, message)
		} else {
			log.Printf("[readPump] No message handler set!")
		}
	}
}

// writePump pumps messages from the hub to the websocket connection
func (c *Client) writePump() {
	defer func() {
		log.Printf("[writePump] Closing connection for client %s", c.id)
		c.conn.Close()
	}()

	log.Printf("[writePump] Started for client %s", c.id)

	for {
		message, ok := <-c.send
		if !ok {
			log.Printf("[writePump] Send channel closed for client %s", c.id)
			c.conn.WriteMessage(websocket.CloseMessage, []byte{})
			return
		}

		log.Printf("[writePump] Writing message to client %s: %s", c.id, string(message)[:min(len(message), 100)])

		w, err := c.conn.NextWriter(websocket.TextMessage)
		if err != nil {
			log.Printf("[writePump] NextWriter error for client %s: %v", c.id, err)
			return
		}
		w.Write(message)

		// Add queued messages to current websocket message
		n := len(c.send)
		for i := 0; i < n; i++ {
			w.Write([]byte("\n"))
			w.Write(<-c.send)
		}

		if err := w.Close(); err != nil {
			log.Printf("[writePump] Close error for client %s: %v", c.id, err)
			return
		}
		log.Printf("[writePump] Message sent successfully to client %s", c.id)
	}
}
