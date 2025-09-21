# TramTue ChatBot AI Backend v2.0

Advanced AI Chatbot Backend với Multi-Agent System, Memory Engine, và RAG Pipeline.

## 🚀 Features

### Core Features
- **Multi-Agent System**: Discovery, Customer Service, Sales, Handoff, Followup agents
- **Memory Engine**: Short-term và long-term memory với user profiling
- **RAG Pipeline**: Document ingestion, chunking, embedding, và vector search
- **Human-like Timing**: Typing simulation với realistic delays
- **Orchestrator**: Intelligent routing giữa các agents

### Technical Features
- **FastAPI**: Modern, fast web framework
- **Supabase**: PostgreSQL database với vector search
- **Gemini AI**: Google's advanced language model
- **Async/Await**: Full asynchronous support
- **Structured Logging**: Comprehensive logging với correlation IDs
- **Health Checks**: Detailed health monitoring
- **Rate Limiting**: API protection
- **CORS Support**: Cross-origin resource sharing

## 📋 Requirements

- Python 3.11+
- PostgreSQL với pgvector extension (Supabase)
- Redis (for caching và background tasks)
- Google Gemini API key

## 🛠️ Installation

### Local Development

1. **Clone repository**
```bash
git clone <repository-url>
cd TramTue-ChatbotAI-BackendV2
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Setup environment variables**
```bash
cp .env.example .env
# Edit .env với your configuration
```

5. **Setup database**
```bash
# Run migrations trong Supabase dashboard
# hoặc execute migrations/001_initial_schema.sql
```

6. **Run application**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker Deployment

1. **Build image**
```bash
docker build -t tramtue-chatbot .
```

2. **Run container**
```bash
docker run -p 8000:8000 --env-file .env tramtue-chatbot
```

### Render.com Deployment

1. **Connect repository** to Render.com
2. **Set environment variables** trong Render dashboard
3. **Deploy** using render.yaml configuration

## ⚙️ Configuration

### Environment Variables

```env
# Application
ENVIRONMENT=development
LOG_LEVEL=INFO
CORS_ORIGINS=*
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key

# AI APIs
GEMINI_API_KEY=your_gemini_api_key

# Redis
REDIS_URL=redis://localhost:6379

# Admin
ADMIN_TOKEN=your_admin_token
```

### Database Schema

Database được setup tự động với migration script:
- `users`: User profiles và settings
- `conversations`: Chat conversations
- `messages`: Individual messages
- `memories`: User memory storage
- `documents`: RAG documents
- `doc_chunks`: Document chunks for RAG
- `doc_embeddings`: Vector embeddings
- `timers`: Scheduled tasks
- `handoffs`: Human handoff requests
- `metrics`: System metrics

## 📚 API Documentation

### Health Endpoints
- `GET /health` - Basic health check
- `GET /health/detailed` - Detailed system status
- `GET /health/ready` - Readiness probe
- `GET /health/live` - Liveness probe

### Chat Endpoints
- `POST /chat/conversations` - Create conversation
- `POST /chat/conversations/{id}/messages` - Send message
- `GET /chat/conversations/{id}/messages` - Get messages
- `PUT /chat/conversations/{id}/state` - Update conversation state
- `GET /chat/users/{id}/profile` - Get user profile
- `POST /chat/users/{id}/memory` - Create memory

### RAG Endpoints
- `POST /rag/ingest/website` - Ingest website
- `POST /rag/ingest/file` - Ingest file
- `POST /rag/search` - Search documents
- `GET /rag/context` - Get context for query
- `GET /rag/stats` - Get RAG statistics

### Timer Endpoints
- `POST /timers/run` - Execute timer task
- `POST /timers` - Create timer
- `GET /timers/user/{id}` - Get user timers
- `PUT /timers/{id}` - Update timer
- `DELETE /timers/{id}` - Cancel timer

### Admin Endpoints
- `POST /admin/reload` - Reload configurations
- `GET /admin/stats` - System statistics
- `GET /admin/users` - List users
- `GET /admin/conversations` - List conversations
- `GET /admin/metrics` - System metrics
- `DELETE /admin/users/{id}/reset` - Reset user data
- `POST /admin/cleanup` - Cleanup old data

## 🏗️ Architecture

### Multi-Agent System

```
User Message → Orchestrator → Agent Router → Specific Agent
                    ↓
Memory Engine ← Response ← Agent Processing ← RAG Context
```

#### Agents
1. **Discovery Agent**: Thu thập thông tin user
2. **Customer Service Agent**: Xử lý complaints và support
3. **Sales Agent**: Tư vấn sản phẩm và bán hàng
4. **Handoff Agent**: Chuyển cho human support
5. **Followup Agent**: Theo dõi sau tương tác
6. **General Chat Agent**: Trò chuyện thông thường

### Memory Engine
- **Short-term Memory**: Recent conversation context
- **Long-term Memory**: User preferences, personal info, health data
- **Profile Building**: Automatic user profiling
- **Context Retrieval**: Relevant memory for responses

### RAG Pipeline
- **Document Ingestion**: Website và file processing
- **Text Chunking**: Intelligent text segmentation
- **Vector Embeddings**: Sentence transformer embeddings
- **Vector Search**: Similarity search trong Supabase
- **Context Generation**: Relevant context for responses

## 🔧 Development

### Code Structure
```
app/
├── api/           # API endpoints
├── core/          # Core functionality (config, database, logging)
├── models/        # Pydantic models
├── services/      # Business logic services
└── main.py        # FastAPI application

migrations/        # Database migrations
tests/            # Test files
```

### Testing
```bash
pytest tests/ -v
```

### Code Quality
```bash
black app/
isort app/
flake8 app/
```

## 📊 Monitoring

### Logging
- Structured logging với structlog
- Correlation IDs for request tracking
- Performance metrics
- Error tracking

### Health Checks
- Database connectivity
- External API availability
- Memory usage
- Response times

### Metrics
- Request counts
- Response times
- Error rates
- Agent usage statistics

## 🚀 Deployment

### Production Checklist
- [ ] Set ENVIRONMENT=production
- [ ] Configure proper CORS_ORIGINS
- [ ] Set strong ADMIN_TOKEN
- [ ] Setup monitoring và alerting
- [ ] Configure backup strategy
- [ ] Setup SSL certificates
- [ ] Configure rate limiting
- [ ] Setup log aggregation

### Scaling
- Horizontal scaling với multiple instances
- Redis for shared caching
- Database connection pooling
- Background task processing với Celery

## 🤝 Contributing

1. Fork repository
2. Create feature branch
3. Make changes
4. Add tests
5. Submit pull request

## 📄 License

MIT License - see LICENSE file for details.

## 🆘 Support

For support và questions:
- Create GitHub issue
- Contact development team
- Check documentation

---

**TramTue ChatBot AI Backend v2.0** - Powered by FastAPI, Supabase, và Google Gemini AI