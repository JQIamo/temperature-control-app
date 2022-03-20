import React from 'react';
import RobustWebSocket from 'robust-websocket';

const timeout = 5000;

class ServerHandler {
    constructor() {
        this.eventHandlers = {};
        this.oneTimeEventHandlers = {};
        this.connectionLost = true;

        this.pingTimeout = null;

        this.onLostConnection = null;
        this.onEstablishedConnection = null;
    }

    setupWebsocket = () => {
        console.log("Server Handler: Establishing websocket connection...");
        const abortCtl = new AbortController();
        const fetchTimeoutId = setTimeout(() => abortCtl.abort(), 2000);
        let connection = false;
        return fetch(
            'websocket', { method: 'GET' }
        ).then(response => response.json()
        ).then(response => {
            if (connection) {
                return response;
            }
            connection = true;
            clearTimeout(fetchTimeoutId);

            if (response.websocket_addr) {
                console.log("Server Handler: Websocket address:", response.websocket_addr);

                this.websocket = new RobustWebSocket(
                    response.websocket_addr, null, {
                        timeout: timeout,
                        shouldReconnect: (event, ws) => {
                            console.log("Server Handler: Connection Lost. Event code: ", event.code);
                            this.connectionLost = true;
                            this.onLostConnection && this.onLostConnection();

                            if (event.type === 'online') return 0;
                            const should = [1006, 1011, 1012].indexOf(event.code);
                            if (Number.isInteger(should)) {
                                console.log("Server Handler: Retrying...");
                                return timeout;
                            }
                            return false;
                        }
                    }
                );

                this.websocket.onopen = () => {
                    console.log("Server Handler: Websocket connection open");
                    this.connectionLost = false;
                    this.websocket.onopen = (() => {
                        console.log("Server Handler: Websocket connection restored");
                        this.connectionLost = false;
                        this.onEstablishedConnection && this.onEstablishedConnection();
                    });
                    this.websocket.onmessage = ((event) => this.messageHandler(event.data));
                    this.onEstablishedConnection && this.onEstablishedConnection();
                };
            }
        }).catch(
            error => {console.error('Server Handler: Websocket Error:', error)}
        );
    }

    establishConnection = () => {
        if (this.connectionLost) {
            this.setupWebsocket();
        }
    }

    closeConnection = () => {
        this.websocket.close();
    }

    sendMessage = (messageObj) => {
        if (!this.connectionLost){
            this.websocket.send(JSON.stringify(messageObj));
        }
    }

    messageHandler = (_message) => {
        const message = JSON.parse(_message);
        if (!message.event) {
            console.error("Server Handler: Received malformed message: ", message);
        }

        const oneTimeHandler = this.oneTimeEventHandlers[message.event];
        if(oneTimeHandler) {
            oneTimeHandler(message);
            delete this.oneTimeEventHandlers[message.event];
        }

        const handler = this.eventHandlers[message.event];
        if (handler) {
            handler(message);
        }

    }

    subscribeTo = (_event, handler) => {
        const message = {
            event: "subscribe",
            subscribe_to: _event
        }
        this.eventHandlers[_event] = handler;
        this.sendMessage(message);
    }

    request = (request, message, handler) => {
        const event = {
            event: request
        };
        this.oneTimeEventHandlers[request] = handler;
        if (message) {
            message = Object.assign(event, message)
            this.sendMessage(message);
        } else {
            this.sendMessage(event);
        }
    }
}

export default ServerHandler;