# Weave CBT

Weave CBT is the intended local Computer-Based Testing runtime for schools using Weave. Each school hosts and controls its own CBT server and database; Weave does not host or own the school's exam database or question bank.

This repository is currently at the architecture and foundation stage. The domains below describe the intended direction and must not be read as a list of completed features.

## System boundary

The school-owned CBT server is authoritative for examination content and execution, including:

- question banks, questions, and answer options;
- exam definitions, schedules, eligibility projections, and PIN credentials;
- candidate attempts, question allocations, answers, and local scoring;
- examination audit records and synchronization state.

Weave remains authoritative for:

- tenant, administrator, teacher, and student identity;
- teacher class-subject assignments and student enrollment;
- assessment schemes and components, grading scales, and final academic results.

The systems communicate through authenticated APIs. Authorized management traffic may reach the local server through a secure tunnel, while student examination traffic is intended to remain primarily on the school's local network.

```text
Weave Cloud
    <->
Authenticated Integration API / Secure Tunnel
    <->
School-Owned CBT Server
    |-- FastAPI backend
    |-- PostgreSQL
    |-- Redis
    |-- background workers
    `-- CBT frontend
    <->
School LAN
    <->
Student Computers
```

## Intended backend domains

- **Node** - installation registration, machine identity, tenant association, integration metadata, versions, and health.
- **Identity** - only the minimal identities, assignment permissions, and short-lived Weave authorization data required by CBT. It must not reproduce Weave's full user-management system.
- **Academics** - minimal references to classes, subjects, assessment components, sessions, and terms owned by Weave.
- **Questions** - the school's local question banks, questions, answer options, and related metadata.
- **Exams** - exam configuration, assessment-component association, lifecycle, question pools, teacher submission, administrator sealing, and versioning.
- **Candidates** - exam rosters, Weave student references, admission numbers, eligibility state, PIN verification, and eligibility versions.
- **Scheduling** - local exam dates, admission windows, duration, activation, and closure.
- **Attempts** - resumable candidate sessions, stable question allocation, persisted answers, server-enforced timing, duplicate-attempt prevention, and submission.
- **Results** - raw CBT scores and the references Weave needs to apply its assessment and grading rules. CBT does not calculate final academic grades.
- **Synchronization** - academic context, eligibility, assignments, results, retries, idempotency, cursors, and versions exchanged with Weave.
- **Audit** - security-sensitive and exam-sensitive events without recording sensitive question content.

Weave-specific transport concerns should remain behind a dedicated adapter such as `app/integrations/weave/`. Domain services should not make arbitrary HTTP requests to Weave directly.

## Architectural rules

1. The school owns the CBT database and question bank.
2. PostgreSQL is the durable source of truth for local exam execution; Redis is only an acceleration and cache layer.
3. Teachers may author content only for class-subject assignments authorized by Weave; administrators finalize and seal exams.
4. Candidate question allocation should be generated once per attempt and preserved for resume and recovery.
5. Correct answers must not be trusted to the frontend. Authoritative scoring occurs on the local FastAPI server.
6. Weave receives academic scores through explicit integration APIs, never by direct database access.
7. An active local exam must remain operable during temporary Weave unavailability.
8. Unrelated Weave domains must not be recreated in this repository.

## Development direction

Work is expected to progress incrementally from database and model foundations through migrations, repositories, services, routes, integration contracts, workers, frontend, resilience, security, and load testing.

This README should be updated as those architectural intentions become concrete implementations.
