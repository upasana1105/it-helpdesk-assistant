# Multi-User Workshop Deployment Guide

This guide provides instructions for running multi-user hands-on labs with the **IT Helpdesk AI Assistant**.

## Overview
When hosting workshops with multiple attendees deploying into a shared GCP project, follow these guidelines to prevent resource naming collisions and ensure proper IAM isolation.

---

## 1. Environment Variable Scoping per User
Each lab attendee should set a unique agent suffix in their `.env` file:
```bash
USER_SUFFIX=attendee-01
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
MODEL_NAME=gemini-3.6-flash
```

---

## 2. Deploying reasoningEngines with Scoped Names
When deploying via `agents-cli`:
```bash
agents-cli deploy --display-name="it-helpdesk-assistant-${USER_SUFFIX}"
```

---

## 3. Verifying Deployment
Attendees can verify their deployed instance using `curl`:
```bash
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Check status of INC-101", "user_id": "attendee_01"}'
```
