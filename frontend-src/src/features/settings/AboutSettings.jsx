import React from "react";
import { Card, Row, Col, Badge } from "react-bootstrap";
import { Info, Github, FileText, Globe } from "lucide-react";

export function AboutSettings() {
  return (
    <section className="settings-pane active animate-fade-in">
      <div className="mb-4 border-bottom pb-3">
        <h2 className="mb-1"><Info className="me-2 text-primary" size={28} />About Rasputin</h2>
        <p className="text-body-secondary mb-0">Version, license, and system information.</p>
      </div>

      <Row className="g-4">
        <Col md={12}>
          <Card className="shadow-sm border-0 bg-primary bg-opacity-10 text-center py-5">
            <Card.Body>
              <div className="display-4 fw-bold text-primary mb-2 tracking-tight">RASPUTIN</div>
              <Badge bg="primary" pill className="fs-6 px-3 py-2 mb-4">v0.2.0-beta</Badge>
              <Badge bg="dark" pill className="fs-6 px-3 py-2 mb-4 ms-2">AGPL-3.0-or-later</Badge>
              <p className="text-muted w-75 mx-auto mb-0">
                The ultimate orchestration engine for autonomous AI capabilities. 
                Built to manage complex knowledge graphs, govern local model execution, 
                and execute missions via WarSat protocol.
              </p>
              <p className="text-muted w-75 mx-auto mt-3 mb-0">
                Rasputin is free software. Users interacting with a modified network version
                must be offered its corresponding source under the GNU Affero GPL.
              </p>
            </Card.Body>
          </Card>
        </Col>

        <Col md={6}>
          <Card className="shadow-sm border-0 h-100">
            <Card.Body>
              <h6 className="fw-bold mb-3">System Information</h6>
              <ul className="list-unstyled mb-0">
                <li className="mb-2 text-muted"><strong className="text-dark">Architecture:</strong> x64</li>
                <li className="mb-2 text-muted"><strong className="text-dark">Runtimes:</strong> Native, Docker, and Desktop</li>
                <li className="mb-2 text-muted"><strong className="text-dark">Engine:</strong> Node.js + Python 3.12</li>
                <li className="mb-0 text-muted"><strong className="text-dark">UI Framework:</strong> React + Vite</li>
              </ul>
            </Card.Body>
          </Card>
        </Col>

        <Col md={6}>
          <Card className="shadow-sm border-0 h-100">
            <Card.Body>
              <h6 className="fw-bold mb-3">Links & Resources</h6>
              <div className="d-grid gap-2">
                <a href="https://github.com/Shingenn5/Rasputin#readme" target="_blank" rel="noreferrer" className="btn btn-light text-start border d-flex align-items-center">
                  <FileText size={18} className="me-3 text-primary" /> Documentation
                </a>
                <a href="https://github.com/Shingenn5/Rasputin" target="_blank" rel="noreferrer" className="btn btn-light text-start border d-flex align-items-center">
                  <Github size={18} className="me-3 text-dark" /> Source Code
                </a>
                <a href="https://github.com/Shingenn5/Rasputin/blob/main/LICENSE" target="_blank" rel="noreferrer" className="btn btn-light text-start border d-flex align-items-center">
                  <Globe size={18} className="me-3 text-info" /> AGPL License
                </a>
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </section>
  );
}
