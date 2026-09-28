# API Contract

## Phase 1 Base
Development API base:
`/api`

A versioned API such as `/api/v1` may be introduced when the public contract stabilizes.

## Standard Compile Request
```json
{
  "input": "I want to make a login page for my website"
}
```

## Standard Compile Response
```json
{
  "input": "I want to make a login page for my website",
  "result": "..."
}
```

## Health
`GET /api/health`

Expected:
```json
{
  "status": "ok",
  "service": "prompt-compiler"
}
```

## Root
`GET /`

Expected:
```json
{
  "name": "Prompt Compiler",
  "version": "0.1.0",
  "status": "running"
}
```

## Planned Endpoints
These are design targets, not necessarily implemented:

- `POST /api/compile`
- `POST /api/analyze`
- `POST /api/interview/start`
- `POST /api/interview/answer`
- `GET /api/templates`
- `GET /api/project/context`
- `POST /api/project/context`
- `GET /api/history`
- `POST /api/feedback`

## Rules
- Validate all API input.
- Return clear errors.
- Do not expose internal stack traces to normal clients.
- Do not claim an endpoint exists until it has been implemented and tested.
- Document deviations from this contract.
