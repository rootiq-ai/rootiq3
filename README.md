# Alert Monitoring MVP with RCA Generation

🚨 **A comprehensive alert monitoring system with automated Root Cause Analysis using RAG and LLM**

This MVP system ingests alerts from various monitoring systems, groups them intelligently, and generates detailed Root Cause Analysis (RCA) reports using Retrieval-Augmented Generation (RAG) with Ollama3 and ChromaDB.

## 🌟 Features

- **Alert Ingestion**: Receive alerts from multiple monitoring systems with unique IDs
- **PostgreSQL Storage**: Robust alert storage with indexing and querying capabilities
- **Intelligent Grouping**: Automatically group alerts by host and service name
- **RAG-powered RCA**: Generate comprehensive RCA reports using historical data
- **Vector Search**: ChromaDB-powered similarity search for incident patterns
- **LLM Integration**: Ollama3 (Llama3) for natural language RCA generation
- **Interactive Dashboard**: Streamlit-based frontend for monitoring and analysis
- **REST API**: FastAPI backend with comprehensive endpoints
- **Real-time Updates**: Live dashboard with auto-refresh capabilities

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│   Monitoring    │───▶│   FastAPI    │───▶│   PostgreSQL   │
│    Systems      │    │   Backend    │    │   Database     │
└─────────────────┘    └──────────────┘    └─────────────────┘
                              │
                              ▼
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│   Streamlit     │◀───│  RAG Service │───▶│    ChromaDB     │
│   Frontend      │    │              │    │ Vector Database │
└─────────────────┘    └──────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌──────────────┐
                       │   Ollama3    │
                       │    (LLM)     │
                       └──────────────┘
```

## 📋 Prerequisites

### System Requirements
- **OS**: Ubuntu 22.04+ (recommended) or compatible Linux distribution
- **Python**: 3.10+
- **RAM**: 8GB minimum (16GB recommended for LLM operations)
- **Storage**: 10GB free space (for models and data)

### Required Services
- **PostgreSQL**: 13+ 
- **Ollama**: Latest version with Llama3 model
- **Python packages**: Listed in requirements.txt files

## 🚀 Quick Start

### Option 1: Using the Setup Script (Recommended)

```bash
# Clone the repository
git clone <your-repository-url>
cd alert-monitoring-mvp

# Make the setup script executable
chmod +x scripts/run_services.sh

# Run the complete setup (this will install everything)
./scripts/run_services.sh
```

### Option 2: Docker Compose (Easiest)

```bash
# Clone the repository
git clone <your-repository-url>
cd alert-monitoring-mvp

# Start all services with Docker Compose
docker-compose up -d

# Pull the Ollama model (required after first startup)
docker exec -it alert-monitoring-ollama ollama pull llama3

# Check service status
docker-compose ps
```

### Option 3: Manual Setup

```bash
# 1. Clone and setup environment
git clone <your-repository-url>
cd alert-monitoring-mvp
python3.10 -m venv venv
source venv/bin/activate

# 2. Install Ollama and pull model
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3

# 3. Setup PostgreSQL
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo -u postgres createdb alertdb
sudo -u postgres createuser alertuser
sudo -u postgres psql -c "ALTER USER alertuser PASSWORD 'alertpass';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE alertdb TO alertuser;"

# 4. Install Python dependencies
cd backend && pip install -r requirements.txt
cd ../frontend && pip install -r requirements.txt

# 5. Setup environment variables
cp .env.example .env
# Edit .env with your configuration

# 6. Initialize databases
python scripts/setup_db.py
python scripts/setup_chromadb.py

# 7. Start services
# Terminal 1 - Backend
cd backend && python -m app.main

# Terminal 2 - Frontend  
cd frontend && streamlit run streamlit_app.py
```

## 🔧 Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Key configuration options:

```bash
# Database
DATABASE_URL=postgresql://alertuser:alertpass@localhost:5432/alertdb

# Ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3

# ChromaDB
CHROMADB_PATH=./chromadb_data
CHROMADB_COLLECTION=alert_knowledge

# RAG Settings
SIMILARITY_THRESHOLD=0.7
TOP_K_SIMILAR=5
MAX_CONTEXT_LENGTH=4000
```

## 📖 Usage

### Accessing the Application

After successful setup:
- **Frontend Dashboard**: http://localhost:8501
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

### API Endpoints

#### Alert Management
```bash
# Ingest a new alert
POST /api/alerts/ingest
{
  "monitoring_system": "prometheus",
  "host_name": "web-server-01", 
  "service_name": "nginx",
  "alert_name": "HighCPUUsage",
  "severity": "high",
  "message": "CPU usage above 90%"
}

# Get alerts
GET /api/alerts?host_name=web-server-01&limit=50

# Get ungrouped alerts
GET /api/alerts/ungrouped/list
```

#### Group Management
```bash
# Create groups from alerts
POST /api/groups/create

# Get groups
GET /api/groups?include_alerts=true

# Get specific group
GET /api/groups/{group_id}
```

#### RCA Generation
```bash
# Generate RCA for a group
GET /api/rca/{group_id}

# Quick analysis
GET /api/rca/{group_id}/quick-analysis

# Search similar incidents
POST /api/rca/search-incidents?query=high cpu usage
```

### Dashboard Features

#### 📊 Dashboard Overview
- Real-time metrics and statistics
- Alert severity distribution
- Top hosts and services by alert count
- Recent activity timeline

#### 🚨 Alerts Management
- View and filter alerts
- Add new alerts manually or via CSV
- Generate sample data for testing
- Detailed alert information and analytics

#### 👥 Groups Management  
- View alert groups
- Create groups from ungrouped alerts
- Group analytics and health monitoring
- Bulk group operations

#### 🔍 RCA Analysis
- Generate comprehensive RCA reports
- Quick analysis for rapid insights
- Search similar historical incidents
- Custom analysis with manual data entry

## 🧪 Testing the System

### Sample Alert Data

```bash
# Generate sample alerts via API
curl -X POST "http://localhost:8000/api/alerts/batch-ingest" \
-H "Content-Type: application/json" \
-d '[
  {
    "monitoring_system": "test",
    "host_name": "web-server-01",
    "service_name": "nginx", 
    "alert_name": "HighCPUUsage",
    "severity": "high",
    "message": "CPU usage above 90% for 5 minutes"
  }
]'

# Create groups
curl -X POST "http://localhost:8000/api/groups/create"

# Generate RCA  
curl -X GET "http://localhost:8000/api/rca/{group_id}"
```

### Using the Dashboard

1. **Add Sample Alerts**: Go to Alerts → Bulk Operations → Generate Sample Alerts
2. **Create Groups**: Go to Groups → Create Groups → Create Alert Groups  
3. **Generate RCA**: Go to RCA Analysis → Generate RCA → Select a group
4. **Explore Features**: Use the dashboard to explore alerts, groups, and RCA reports

## 🛠️ Development

### Project Structure

```
alert-monitoring-mvp/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── api/            # API endpoints
│   │   ├── models/         # Database models
│   │   ├── services/       # Business logic
│   │   ├── database/       # Database configuration
│   │   └── config/         # Settings and configuration
│   └── requirements.txt
├── frontend/               # Streamlit frontend
│   ├── components/         # UI components  
│   ├── streamlit_app.py   # Main application
│   └── requirements.txt
├── scripts/               # Setup and utility scripts
│   ├── setup_db.py       # Database initialization
│   ├── setup_chromadb.py # ChromaDB setup
│   └── run_services.sh   # Service runner
├── docker-compose.yml    # Docker configuration
├── .env.example         # Environment template
└── README.md           # This file
```

### Adding New Features

1. **Backend**: Add endpoints in `backend/app/api/`
2. **Frontend**: Add components in `frontend/components/`
3. **Models**: Define database models in `backend/app/models/`
4. **Services**: Implement business logic in `backend/app/services/`

### Running Tests

```bash
# Backend tests (if implemented)
cd backend && python -m pytest

# Frontend tests (if implemented) 
cd frontend && python -m pytest

# Manual API testing
curl -X GET "http://localhost:8000/health"
```

## 🔍 Troubleshooting

### Common Issues

#### "Connection refused" errors
```bash
# Check if services are running
./scripts/run_services.sh status

# Check ports
netstat -tulpn | grep -E "(5432|8000|8501|11434)"

# Restart services
./scripts/run_services.sh restart
```

#### Ollama model not found
```bash
# Pull the model manually
ollama pull llama3

# Check available models
ollama list

# Check Ollama service
curl http://localhost:11434/api/tags
```

#### Database connection issues
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Test connection
psql -h localhost -U alertuser -d alertdb -c "SELECT 1;"

# Reset database
python scripts/setup_db.py
```

#### ChromaDB issues
```bash
# Reset ChromaDB
rm -rf ./chromadb_data
python scripts/setup_chromadb.py
```

### Service Logs

```bash
# View service logs
./scripts/run_services.sh logs

# Individual service logs
tail -f /tmp/backend.log
tail -f /tmp/frontend.log

# Docker logs
docker-compose logs -f backend
docker-compose logs -f frontend
```

## 📈 Performance Optimization

### Database Optimization
- Indexes are automatically created on frequently queried columns
- Use pagination for large result sets
- Consider partitioning for high-volume deployments

### RAG Performance  
- Adjust `SIMILARITY_THRESHOLD` to balance relevance vs. speed
- Limit `TOP_K_SIMILAR` for faster searches
- Use smaller embedding models for faster processing

### LLM Performance
- Use faster Ollama models like `llama3:8b` for quicker responses
- Adjust `MAX_CONTEXT_LENGTH` to balance detail vs. speed
- Consider GPU acceleration for Ollama

## 🚀 Production Deployment

### Security Considerations
- Change default passwords in `.env`
- Enable SSL/TLS for all services
- Set up proper firewall rules
- Use secrets management for sensitive data

### Scaling
- Use load balancers for multiple backend instances
- Implement Redis for session storage
- Consider read replicas for PostgreSQL
- Use message queues for background tasks

### Monitoring
- Set up health checks for all services
- Monitor resource usage (CPU, memory, disk)
- Implement logging aggregation
- Set up alerts for service failures

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and test thoroughly
4. Commit your changes: `git commit -am 'Add new feature'`
5. Push to the branch: `git push origin feature-name`
6. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **Ollama**: For providing excellent LLM serving capabilities
- **ChromaDB**: For vector database functionality  
- **FastAPI**: For the robust API framework
- **Streamlit**: For the interactive dashboard framework
- **PostgreSQL**: For reliable data storage

## 📞 Support

For issues and questions:
1. Check the troubleshooting section above
2. Search existing GitHub issues
3. Create a new issue with detailed information
4. Include logs and error messages

---

**🎉 Happy monitoring and analyzing!** 

This MVP provides a solid foundation for alert monitoring with AI-powered RCA generation. Feel free to extend and customize it for your specific needs.
