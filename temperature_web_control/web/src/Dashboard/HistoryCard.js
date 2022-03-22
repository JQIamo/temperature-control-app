import React from 'react';
import Plot from 'react-plotly.js';
import Card from 'react-bootstrap/Card'
import {GraphUp} from "react-bootstrap-icons";

function HistoryCard(props) {
    const layout = {
        margin: {
            l: 70,
            r: 50,
            b: 50,
            t: 20,
            pad: 4
        },
        height: 300,
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: {
            size: 10,
            color: 'white'
        },
        xaxis: {
            gridcolor: "rgba(255,255,255,0.25)",
            type: 'date'
        },
        yaxis: {
            gridcolor: "rgba(255,255,255,0.25)",
            title: {
                text: 'Temperature / °C',
            }
        }
    };
    return (
        <Card className="mb-3 border-info">
            <Card.Header> <GraphUp /> History </Card.Header>
            <Plot
                data={props.data}
                layout={layout}
            />
        </Card>
    );
}

export default HistoryCard;