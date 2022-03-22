import {Modal, Container, Spinner, Button} from "react-bootstrap";
import {ArrowClockwise, WifiOff} from "react-bootstrap-icons";

function LostConnectionModal(props) {
    return (
        <Modal
            show={props.show}
            backdrop="static"
            keyboard={false}
        >
            <Modal.Header>
                <Modal.Title><WifiOff /> Lost connection</Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <p>Lost connection to the server.</p>
                <p>Trying to reconnect...</p>
                <Container className="d-flex justify-content-center">
                    <Spinner animation="border" role="status">
                        <span className="visually-hidden">Loading...</span>
                    </Spinner>
                </Container>
            </Modal.Body>
            <Modal.Footer>
                <Button variant="secondary" onClick={() => {window.location.reload();}}>
                    <ArrowClockwise /> Reload
                </Button>
            </Modal.Footer>
        </Modal>
    );
}

export default LostConnectionModal;