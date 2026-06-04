import React from "react";
import { Button, Card, Form, Stack } from "react-bootstrap";

export function LoginShell({ onSubmit, status }) {
  return (
    <section className="login-shell" id="loginShell">
      <Card className="login-card shadow-sm" data-testid="login-card">
        <Card.Body>
          <form onSubmit={onSubmit} data-testid="login-form">
            <Stack gap={3}>
              <div className="brand-mark large">R</div>
              <div>
                <h1>Rasputin</h1>
                <p className="text-body-secondary mb-0">Private local workbench. Sign in with your local admin password.</p>
              </div>
              <Form.Group controlId="loginUsername">
                <Form.Label>Username</Form.Label>
                <Form.Control name="username" defaultValue="admin" autoComplete="username" />
              </Form.Group>
              <Form.Group controlId="loginPassword">
                <Form.Label>Password</Form.Label>
                <Form.Control name="password" type="password" autoComplete="current-password" required />
              </Form.Group>
              <Button type="submit" className="w-100">Sign In</Button>
              {status && <p className="text-body-secondary small mb-0">{status}</p>}
            </Stack>
          </form>
        </Card.Body>
      </Card>
    </section>
  );
}
