# SUVIDHA PRD

---

# Suvidha
## From Conversation to Confirmation

---

## Vision

Suvidha is an AI welfare concierge that enables India's informal workforce to discover, apply for, and successfully avail government welfare schemes through multilingual voice conversations and intelligent document processing.

Unlike existing portals that stop at information or form generation, Suvidha completes the entire journey---from identifying eligible schemes to preparing and (where integrations are available) submitting the application.

**North Star**

> A domestic worker should be able to successfully access a government benefit within minutes using only a conversation in their preferred language.

---

## Problem

Government welfare schemes often go unclaimed because citizens struggle with:
- Discovering relevant schemes
- Understanding eligibility
- Collecting the right documents
- Filling lengthy forms
- Uploading documents correctly
- Correcting mistakes
- Submitting applications
- Tracking status

Most users abandon the journey before completion.

Suvidha removes these barriers through a single conversational experience.

---

## Target Users

- Domestic workers
- Cooks
- Drivers
- Barbers
- Construction workers
- Electricians
- Plumbers
- Street vendors
- Sanitation workers
- Daily wage workers

---

## Product Goal

Take the user from:

> "I don't know what benefits I can get."

to

> "My application has been successfully submitted and I'm ready to receive the benefit."

---

## End-to-End Journey

1. Voice conversation in the user's language
2. Eligibility discovery
3. Personalized scheme recommendations
4. Document upload
5. AI document extraction
6. Automatic form prefill
7. Voice collection of missing fields
8. Validation of required information
9. Application package generation
10. Submission (real integration if available, otherwise demo simulation)
11. Confirmation with application/reference ID and next steps

The conversation ends only when the user's job is completed.

---

## Demo Story

Lakshmi, a Kannada-speaking domestic worker, opens Suvidha.

She simply says:
> "I work as a maid."

Suvidha:
- Understands her profile
- Determines eligible schemes
- Explains why she qualifies
- Requests Aadhaar and Income Certificate
- Extracts information using Sarvam Document AI
- Auto-fills the application
- Collects one or two missing fields through voice
- Submits (or simulates submission for demo)
- Displays:
  - Application Submitted
  - Reference Number
  - Expected Processing Timeline
  - Required follow-up (if any)

---

## Product Philosophy

We are **not** building:
- A government chatbot
- A scheme search engine
- An OCR demo
- A voice assistant

We are building:

> **An AI welfare autopilot that takes citizens from confusion to successful enrollment.**

---

## Core Capabilities

### Sarvam Voice
- Multilingual conversation
- Speech-to-text
- Text-to-speech
- Collect missing information
- Explain eligibility

### Sarvam Document AI
- Extract structured fields
- Read Aadhaar, PAN, Income Certificates
- Eliminate repetitive data entry

### Suvidha Intelligence
- Eligibility engine
- Form mapping
- Workflow orchestration
- Submission pipeline
- Status tracking

---

## MVP Scope

Support:
- One state (or national schemes)
- 3--5 government schemes
- One polished end-to-end journey

**Golden Flow**

`Open App → Talk → Eligibility → Recommendation → Upload Documents → AI Extraction → Auto-fill → Voice Completion → Submit → Confirmation`

**Success Metric**

The user completes:

`Discover → Verify → Apply → Avail`

without typing.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js + Tailwind + TypeScript |
| Backend | FastAPI / Node.js |
| Database | Supabase |
| Deployment | Vercel |
| LLM | Claude/OpenAI (orchestration only) |
| Voice | Sarvam Voice APIs |
| Document AI | Sarvam Document AI |

---

## Features NOT to Build

- Authentication
- Admin panel
- Analytics
- Notifications
- Payments
- Generic chatbot
- RAG
- Vector DB
- Multi-agent architecture
- Feature-heavy dashboards

---

## Build Order

1. UI
2. Voice conversation
3. Eligibility engine
4. Scheme recommendation
5. Document upload
6. Document extraction
7. Auto-fill
8. Voice completion
9. Submission flow
10. Confirmation screen
11. Polish & demo

---

## One-Sentence Pitch

Suvidha is an AI welfare concierge that helps India's informal workforce discover, apply for, and successfully avail government benefits through multilingual voice conversations and intelligent document processing---transforming a complex government process into a simple conversation.
