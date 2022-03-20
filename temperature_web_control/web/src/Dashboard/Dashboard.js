import React from 'react';

import Container from 'react-bootstrap/Container'
import Row from 'react-bootstrap/Row'
import Col from 'react-bootstrap/Col'

import ServerHandler from "../ServerHandler";

import StatusCard from "./StatusCard";
import ProgramsCard from "./ProgramsCard"
import HistoryCard from "./HistoryCard";
import LostConnectionModal from "../LostConnectionModal";
import update from "immutability-helper";
import QuickActionCard from "./QuickActionCard";

const maxHistoryLength = 1440;

class Dashboard extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            lostConnection: false,
            deviceStatus: {},
            currentPrograms: null,
            programs: [],
            actions: {},
            data: null,
        };
        this.serverHandler = new ServerHandler();
        this.serverHandler.establishConnection();
    }

    componentDidMount = () => {
        this.serverHandler.onEstablishedConnection = () => {
            this.setState({lostConnection: false});
            this.subscribeToServerEvent();
            this.requestControlInfo();
            this.requestInfo();
        };
        this.serverHandler.onLostConnection = () => { this.setState({lostConnection: true}) };

        if (this.serverHandler.connectionLost) {
            this.setState({lostConnection: true});
       } else {
            this.subscribeToServerEvent();
            this.requestControlInfo();
        }
    }

    componentWillUnmount = () => {
        this.serverHandler.closeConnection();
    }

    subscribeToServerEvent = () => {
        this.serverHandler.subscribeTo(
            "status_available",
            (message) => this.deviceStatusUpdate(message.status)
        );
        this.serverHandler.subscribeTo(
            "control_changed",
            (message) => this.requestControlInfo()
        );
    }

    requestInfo = () => {
        this.serverHandler.request('request_status', null, (message) => {
            if (this.checkRequestError(message)) {
                this.deviceStatusUpdate(message.status)
                this.initHistory(Object.keys(message.status));
            }
        });
        this.serverHandler.request('fetch_history', null, (message) => {
            if (this.checkRequestError(message)) {
                this.setHistory(message);
            }
        });
    }

    requestControlInfo = () => {
        this.serverHandler.request('list_actions', null, (message) => {
            if (this.checkRequestError(message)) {
                this.setState({ actions: message.actions, });
            }
        });
        this.serverHandler.request('list_programs', null, (message) => {
            if (this.checkRequestError(message)) {
                this.setState({ programs: message.programs, });
            }
        });
        this.serverHandler.request('current_programs', null, (message) => {
            if (this.checkRequestError(message)) {
                this.setState({ currentPrograms: message.current_programs, });
            }
        });
    }

    runPredefinedProgram = (programName) => {
        this.serverHandler.request('run_predefined_program',{ program: programName }, this.checkRequestError);
    }

    stopProgram = (program) => {
        this.serverHandler.request('abort_program',{ program: program }, this.checkRequestError);
    }

    runProgram = (program) => {
        console.log(program);
        this.serverHandler.request('run_program', program, this.checkRequestError);

    }

    standbyDevice = (deviceName) => {
        this.serverHandler.request('standby_device',{ device: deviceName }, this.checkRequestError);
    }

    deviceStatusUpdate = (statusDict) => {
        this.setState({ deviceStatus: statusDict });
        this.appendHistory(statusDict);
    }

    checkRequestError = (result) => {
        if (result.result !== "ok") {
            // TODO
            console.log("Server returned error: ", result.error_msg);
            return false;
        }
        return true;
    }

    initHistory = (deviceNames) => {
        this.setState({
            data: [
                deviceNames.map((deviceName, i) => {
                    return {
                        x: [],
                        y: [],
                        type: 'scatter',
                        mode: 'lines',
                        name: deviceName,
                    };
                })
            ]
        });
    }

    setHistory = (dataDict) => {
        const data = dataDict.data;
        const newData = Object.keys(data).map((dev, i) => {
            const time = data[dev].time.map((time, i) => {
                return new Date(time  * 1000);
            });

            if (time.length < maxHistoryLength) {
                return {
                    x: time,
                    y: data[dev].temperature,
                    type: 'scatter',
                    mode: 'lines',
                    name: dev,
                };
            } else {
                const _time = time.splice(time.length - maxHistoryLength, maxHistoryLength);
                const _temperature = data[dev].temperature.splice(time.length - maxHistoryLength, maxHistoryLength);

                return {
                    x: _time,
                    y: _temperature,
                    type: 'scatter',
                    mode: 'lines',
                    name: dev,
                };
            }
        });
        this.setState({
            data: newData
        });
    }

    appendHistory = (statusDict) => {
        if (!this.state.data) {
            return;
        }
        const deviceToIndex = {};
        this.state.data.map((item, i) => {
            deviceToIndex[item.name] = i;
        });

        const deleteCmd = {};
        for (const [dev, statusEntries] of Object.entries(statusDict)) {
            const ind = deviceToIndex[dev];
            if (this.state.data[ind].x.length >= maxHistoryLength) {
                deleteCmd[ind] = {};
                deleteCmd[ind].x = {$splice: [[0, this.state.data[ind].x.length - maxHistoryLength + 1]]};
                deleteCmd[ind].y = {$splice: [[0, this.state.data[ind].x.length - maxHistoryLength + 1]]};
            }
        }

        let oldData = this.state.data;
        if (Object.keys(deleteCmd).length > 0) {
            oldData = update(oldData, deleteCmd);
        }

        const updateCmd = {};
        for (const [dev, statusEntries] of Object.entries(statusDict)) {
            const ind = deviceToIndex[dev];
            updateCmd[ind] = {};
            updateCmd[ind].x = {$push: [Date.now()]};
            updateCmd[ind].y = {$push: [statusEntries.temperature]};
        }
        const newData = update(oldData, updateCmd);
        this.setState({
            data: newData
        });
    }

    render = () => {
        const statusCards = Object.keys(this.state.deviceStatus).map((name, i) => {
            const status = this.state.deviceStatus[name];
            return (
                <Col className="mb-4" key={name}>
                    <StatusCard
                                name={name}
                                temperature={status.temperature}
                                controlEnabled={status.control_enabled}
                                setpoint={status.setpoint}
                                currentAction={status.current_action}
                                currentProgram={status.current_program}
                                actionLookup={this.state.actions}
                                status={status.status}
                                stopProgramHandler={this.stopProgram}
                                standbyHandler={this.standbyDevice}
                    />
                </Col>
            );
        });

        return (
            <>
                <Container className="p-3">
                    <Row>
                        <Col>
                            <Row className="row-cols-1 row-cols-sm-1 row-cols-md-1 row-cols-lg-2">
                                {statusCards}
                            </Row>
                        </Col>
                        <Col>
                            <HistoryCard data={this.state.data} />
                        </Col>
                    </Row>
                </Container>
                <Container className="p-2">
                    <h2>Actions</h2>
                    <hr />
                    <Row>
                        <Col>
                            <ProgramsCard
                                programList={this.state.programs}
                                currentPrograms={this.state.currentPrograms}
                                runProgramHandler={this.runPredefinedProgram}
                                stopProgramHandler={this.stopProgram}
                            />
                        </Col>
                        <Col>
                            <QuickActionCard
                                actionLookup={this.state.actions}
                                status={this.state.deviceStatus}
                                runHandler={this.runProgram}
                            />
                        </Col>
                    </Row>
                </Container>

                <LostConnectionModal show={this.state.lostConnection} />
            </>
        );
    }
}

export default Dashboard;