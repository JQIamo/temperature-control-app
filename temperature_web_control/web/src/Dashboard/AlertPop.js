import {Alert, Button} from "react-bootstrap";
import {ExclamationTriangleFill} from "react-bootstrap-icons";

function AlertPop(props) {
    return (
        <Alert show={props.show} variant="danger">
            <Button type="button" className="btn-close float-end" onClick={props.dismissHandler} />
            <ExclamationTriangleFill />
            <strong> Server returned error: </strong> <br />
            { props.error }
        </Alert>
    )
}

export default AlertPop;