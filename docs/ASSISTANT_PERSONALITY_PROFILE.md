# Assistant personality profile

Rasputin's identity is owner-scoped and persisted through the existing
`/api/assistant/profile` contract. The profile changes presentation only; it
cannot widen context authority, grant model containers host access, or bypass
the approval broker.

## Supported fields

```json
{
  "displayName": "Rasputin",
  "persona": {
    "summary": "A dryly sarcastic, respectful local systems partner.",
    "style": {
      "tone": "dry",
      "sarcasm": "light",
      "respectful": true
    }
  }
}
```

The allowed tones are `dry`, `direct`, and `warm`. Sarcasm is bounded to
`off`, `light`, or `moderate`; `respectful` is always forced to `true` by the
backend. Invalid values fall back to the current safe profile rather than
becoming arbitrary policy text. Rasputin is the current placeholder name and
can be changed without changing the stable `assistant_id` (`rasputin`).

The Assistant view exposes these controls beside the identity card. It also
exposes the allowlisted command router as a preview form. A recognized command
still reports `review_required`; only the existing plan, approval, and broker
handoff flow can reach a host adapter.
