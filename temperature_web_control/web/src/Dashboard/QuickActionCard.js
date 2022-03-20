import React from 'react';
import {Card, Accordion, Form, Container, Button} from "react-bootstrap";


class QuickActionAccordionItem extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            values: {},
            targetDevice: null,
        };
    }

    handleRun = () => {
        const action = this.props.action;

        let device = this.state.targetDevice;

        this.props.runHandler({
            steps : [ [{
                action: action.name,
                device: device,
                params: this.state.values
            } ] ]
        });
    }

    handleChangeValue = (param, event) => {
        this.setState({values: Object.assign(this.state.values, {[param] : event.target.value})});
    }

    handleChangeDevice = (event) => {
        this.setState({targetDevice: event.target.value});
    }

    render = () => {
        const action = this.props.action;

        const formInputs = action.params_desc.map((paramTuple, i) => {
            const [param, desc] = paramTuple;
            const id = action.name + "." + param;

            return (
                <Form.Group key={id}>
                    <Form.Label className="mt-4" htmlFor={id}>{ param }</Form.Label>
                    <Form.Control id={id} value={this.state.values[param]} onChange={
                        (event) => {this.handleChangeValue(param, event)}
                    }/>
                    <Form.Text className="text-muted">
                        { desc }
                    </Form.Text>
                </Form.Group>
            );
        });

        const deviceOptions = this.props.status ? Object.keys(this.props.status).map((dev, i) => {
                    return (<option key={dev} value={dev}>{dev}</option>);
                }) : [];

        return (
            <Accordion.Item eventKey={action.name}>
                <Accordion.Header>{action.display_name}</Accordion.Header>
                <Accordion.Body className="bg-secondary">
                    <Container>
                        <Form.Group>
                            <strong>{action.name}</strong>: {action.description}
                        </Form.Group>
                        <Form.Group className="mt-4">
                            <Form.Label htmlFor={action.name + "._device"}>Target Device</Form.Label>
                            <Form.Select value={this.state.targetDevice}
                                         id={action.name + "._device"} onChange={this.handleChangeDevice}>
                                { deviceOptions }
                            </Form.Select>
                        </Form.Group>
                        { formInputs }
                        <Button className="my-4" onClick={this.handleRun}>Run</Button>
                    </Container>
                </Accordion.Body>
            </Accordion.Item>
        );
    }

    componentDidUpdate = () => {
        if (this.props.action) {
            for (const paramTuple of this.props.action.params_desc) {
                const [param, desc] = paramTuple;
                if (this.state.values[param] === undefined){
                    this.setState({values: Object.assign(this.state.values, {[param] : 0})} );
                }
            }
        }

        if (!this.state.targetDevice && this.props.status && Object.keys(this.props.status).length > 0) {
            this.setState({targetDevice: (Object.keys(this.props.status))[0]});
        }
    }
}
 function QuickActionCard(props){
     return (
         <Card className="mb-3">
             <Card.Header> Quick Actions </Card.Header>
             <Accordion>
                 {
                     Object.values(props.actionLookup ? props.actionLookup : {}).map((action, i) => {
                         if (action.standalone) {
                             return (<QuickActionAccordionItem
                                 key={action.name}
                                 action={action}
                                 status={props.status}
                                 runHandler={props.runHandler}
                             />);
                         }
                     })
                 }
             </Accordion>
         </Card>
     );
 }

export default QuickActionCard;
