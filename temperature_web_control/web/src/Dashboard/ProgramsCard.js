import React from 'react';

import { Button, Card, ListGroup, ListGroupItem } from 'react-bootstrap'
import {CardChecklist, CaretRightFill, StopFill} from 'react-bootstrap-icons';

function RunButton(props) {
    return (
        <Button
            className="ml-auto px-4 btn-block"
            onClick={() => {props.runProgramHandler(props.name)}}
        >
            <CaretRightFill width={30} height={30} />
        </Button>
    );
}

function StopButton(props) {
    return (
        <Button
            className="ml-auto px-4 btn-block btn-danger"
            onClick={() => {props.stopProgramHandler(props.name)}}
        >
            <StopFill width={30} height={30} />
        </Button>
    );
}

function ProgramListItem(props) {
    const activeClass = "bg-warning";

    let controlBtn;
    if (props.active) {
        controlBtn = (<StopButton name={props.name} stopProgramHandler={props.stopProgramHandler}/>);
    } else {
        controlBtn = (<RunButton name={props.name} runProgramHandler={props.runProgramHandler}/>);
    }

    return (
        <div className="d-flex align-items-stretch">
            <ListGroupItem className={"flex-fill " + (props.active ? activeClass : "")}
            >
                <div>
                    <div className="d-flex w-100 justify-content-between">
                        <h4 className="mb-1">{ props.name }</h4>
                        { props.active ? (<small className="blinking">Running</small>) : null }
                    </div>
                    <p className="mb-1">{ props.description }</p>
                </div>
            </ListGroupItem>
            { controlBtn }
        </div>
    );
}

function ProgramsCard(props) {
    const programList = props.programList;
    const currentPrograms = props.currentPrograms;

    const programListElements = programList.map((program, i) => {
        const active = currentPrograms && currentPrograms.includes(program.name);
        return <ProgramListItem key={program.name}
                                name={program.name}
                                description={program.description}
                                active={active}
                                runProgramHandler={props.runProgramHandler}
                                stopProgramHandler={props.stopProgramHandler}
        />
    });

    return (
        <Card className="mb-3">
            <Card.Header> <CardChecklist /> Programs </Card.Header>
            <ListGroup > { programListElements } </ListGroup>
        </Card>
    );
}

export default ProgramsCard;