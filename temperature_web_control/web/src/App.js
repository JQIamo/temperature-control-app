import './App.scss';
import React from 'react';
import WebFont from 'webfontloader';

import Button from 'react-bootstrap/Button';
import Container from 'react-bootstrap/Container'

// Icons
import { ThermometerHalf, Speedometer2, Gear } from 'react-bootstrap-icons';

// Components
import Dashboard from './Dashboard/Dashboard'

function NavItem(props) {
    let icon = React.createElement(props.icon, {
        width: 24,
        height: 24,
        className: "d-block mx-auto mb-1"
    });

    const isCurrent = props.currentPage === props.name;

    return (
        <li>
            <a href="#" className={"nav-link" + (isCurrent ? " text-secondary" : "")}>
                {icon}
                {props.name}
            </a>
        </li>
    );
}

class App extends React.Component {
    constructor(props) {
        super(props);
        this.pages = [
            {name: "Dashboard", icon: Speedometer2},
            // {name: "Settings", icon: Gear}
        ];
        this.state = {
          currentPage: "Dashboard",
        };
    }

    componentDidMount = () => {
        WebFont.load({
            google: {
                families: ['B612']
            }
        });
        document.title = "Temperature Control";
    }

    render = () => {
        return (
            <Container className="App" style={ { fontFamily: "B612" } }>
                <header className="App-header d-flex flex-wrap justify-content-center py-3 mb-4 border-bottom">
                    <a href="/"
                       className="d-flex align-items-center mb-3 mb-md-0 me-md-auto text-decoration-none">
                        <h1 className="fs-4">
                            <ThermometerHalf width={40} height={40}/>
                            Temperature Controller App
                        </h1>
                    </a>

                    <ul className="nav col-12 col-lg-auto my-2 justify-content-center my-md-0 text-small">
                        {this.pages.map((page, i) => (
                            <NavItem key={page.name} name={page.name} icon={page.icon} currentPage={this.state.currentPage} />
                        ))}
                    </ul>
                </header>
                <Dashboard />
            </Container>
        );
    }
}

export default App;
