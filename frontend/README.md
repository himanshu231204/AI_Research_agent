# AI Research Agent Frontend

Production-grade AI operations interface for the AI Research Agent.

## Features

- **Streaming Chat Interface** - Real-time AI chat with markdown rendering, syntax highlighting, and source citations
- **Workflow Visualization** - Live LangGraph workflow graph showing agent execution paths
- **Agent Activity Panel** - Real-time monitoring of all active agents with status, duration, and token usage
- **Research Timeline** - Detailed timeline of research events including searches, reflections, and citations
- **Memory Inspector** - Visual exploration of semantic and episodic memory
- **Queue Monitoring** - Celery queue depth and worker health monitoring
- **Model Routing Dashboard** - GPU status, model providers, and routing visualization
- **Observability Dashboard** - Latency, cost, and task metrics with interactive charts

## Tech Stack

- **Next.js 14** - React framework with App Router
- **TypeScript** - Type-safe development
- **TailwindCSS** - Utility-first styling
- **ShadCN UI** - Component library
- **Zustand** - State management
- **TanStack Query** - Server state management
- **Recharts** - Data visualization
- **Framer Motion** - Animations
- **WebSockets** - Real-time updates

## Getting Started

### Prerequisites

- Node.js 18+
- npm or yarn

### Installation

```bash
# Install dependencies
npm install

# Copy environment variables
cp .env.example .env.local

# Run development server
npm run dev
```

### Environment Variables

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
NEXT_PUBLIC_API_PREFIX=/api/v1
```

## Project Structure

```
frontend/
├── app/                    # Next.js App Router pages
│   ├── layout.tsx         # Root layout
│   ├── page.tsx           # Home page (Chat)
│   ├── workflow/          # Workflow visualization
│   ├── agents/            # Agent panel
│   ├── memory/            # Memory inspector
│   ├── queue/             # Queue monitoring
│   ├── models/            # Model routing
│   └── observability/     # Observability dashboard
├── components/            # Reusable UI components
│   ├── ui/               # ShadCN components
│   └── layout/           # Layout components
├── features/             # Feature-specific components
│   ├── chat/             # Chat interface
│   ├── agents/           # Agent panel
│   ├── workflow/         # Workflow graph
│   ├── timeline/         # Research timeline
│   ├── memory/           # Memory inspector
│   ├── queue/            # Queue monitor
│   ├── models/           # Model dashboard
│   └── observability/    # Observability charts
├── hooks/               # Custom React hooks
├── lib/                 # Utilities
├── services/            # API client
├── stores/              # Zustand stores
├── types/               # TypeScript types
└── websocket/           # WebSocket service
```

## Scripts

```bash
# Development
npm run dev              # Start development server
npm run build           # Build for production
npm run start           # Start production server

# Linting & Type Checking
npm run lint            # Run ESLint
npm run type-check      # Run TypeScript check

# Testing
npm run test            # Run tests
npm run test:coverage   # Run tests with coverage
npm run test:ui         # Run tests with UI

# Formatting
npm run format          # Format code with Prettier
```

## Docker

```bash
# Build Docker image
docker build -t research-agent-frontend .

# Run container
docker run -p 3000:3000 research-agent-frontend

# Or use docker-compose
docker-compose up -d
```

## API Integration

The frontend integrates with the following backend APIs:

- **Research API** - Create and manage research tasks
- **Memory API** - Search and retrieve memory entries
- **Models API** - Model status, telemetry, and routing
- **WebSocket** - Real-time updates for streaming and agent activity

## Testing

The project includes unit tests for:

- UI components
- Utility functions
- State management stores

Run tests with:
```bash
npm run test
```

## License

MIT