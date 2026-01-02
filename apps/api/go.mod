module github.com/ersantana/distributed-systems-learning/apps/api

go 1.23

require (
	github.com/ersantana/distributed-systems-learning/packages/core v0.0.0
	github.com/ersantana/distributed-systems-learning/packages/network v0.0.0
	github.com/ersantana/distributed-systems-learning/packages/protocol v0.0.0
	github.com/ersantana/distributed-systems-learning/packages/simulation v0.0.0
	github.com/google/uuid v1.6.0
	github.com/gorilla/websocket v1.5.3
)

replace github.com/ersantana/distributed-systems-learning/packages/protocol => ../../packages/protocol

replace github.com/ersantana/distributed-systems-learning/packages/simulation => ../../packages/simulation

replace github.com/ersantana/distributed-systems-learning/packages/network => ../../packages/network

replace github.com/ersantana/distributed-systems-learning/packages/core => ../../packages/core
