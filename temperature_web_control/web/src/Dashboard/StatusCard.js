import React from 'react';

import Card from 'react-bootstrap/Card'
import Badge from "react-bootstrap/Badge";
import Button from "react-bootstrap/Button";
import {Thermometer, GraphUp} from "react-bootstrap-icons";

function StopButton(props) {
    return (
        <Button
            className="ms-auto btn-block btn-danger float-end btn-sm"
            onClick={() => {props.stopProgramHandler(props.currentProgram)}}
        >
            STOP
        </Button>
    );
}

function DisengageButton(props) {
    return (
        <Button
            className="ms-auto btn-block btn-info float-end btn-sm"
            onClick={() => {props.standbyHandler(props.device)}}
        >
            Disengage
        </Button>
    );
}

function StatusCard(props) {
    let stateStyle = "bg-dark";
    let badgeStyle = "bg-dark";
    let badgeText = "Standby";
    let button;

    if (props.controlEnabled === true) {
        stateStyle = "bg-primary";
        badgeStyle = "bg-primary";
        badgeText = "Active";
        button = ( <DisengageButton
            standbyHandler={props.standbyHandler}
            device={props.name}
        />);
    }

    if (props.currentProgram) {
        stateStyle = "bg-info text-dark";
        badgeStyle = "bg-info";

        button = ( <StopButton
            stopProgramHandler={props.stopProgramHandler}
            currentProgram={props.currentProgram}
        /> );
    }

    if (props.currentAction && props.actionLookup) {
        const currentAction = props.actionLookup[props.currentAction]
        badgeText = currentAction.status_word;
        if (currentAction.attention_level === 0) {
            stateStyle = "bg-info text-dark";
            badgeStyle = "bg-info";
        } else if (currentAction.attention_level === 1) {
            stateStyle = "bg-warning-blinking";
            badgeStyle = "bg-warning";
        }
    }

    const temperature = props.temperature ? props.temperature.toFixed(1) : "--.--";
    const setpoint = props.setpoint ? props.setpoint.toFixed(1) : "--.--";


    return (
        <Card className={stateStyle + " mb-3"}>
            <Card.Header className="text-white">
                <Thermometer /> {props.name}
                <Badge className={badgeStyle + " mx-2"}>
                    {badgeText}
                </Badge>
            </Card.Header>
            <Card.Body>
                <h1 className="display-4">{temperature} °C</h1>
                <div className="d-flex flex-row mt-2">
                    <div className="p-1 text-muted">SETPOINT {setpoint} °C</div>
                    { button }
                </div>
            </Card.Body>
        </Card>
    );
}

export default StatusCard;
