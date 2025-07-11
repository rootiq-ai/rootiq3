#!/bin/bash

# Alert Monitoring MVP - Service Runner Script
# This script starts all necessary services for the application

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if a port is in use
port_in_use() {
    if command_exists lsof; then
        lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null 2>&1
    elif command_exists netstat; then
        netstat -tuln | grep ":$1 " >/dev/null 2>&1
    else
        # Fallback: try to connect to the port
        timeout 1 bash -c "</dev/tcp/localhost/$1" >/dev/null 2>&1
    fi
}

# Function to wait for a service to be ready
wait_for_service() {
    local host=$1
    local port=$2
    local service_name=$3
    local max_attempts=30
    local attempt=1

    print_status "Waiting for $service_name to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s -f "http://$host:$port/health" >/dev/null 2>&1 || \
           curl -s -f "http://$host:$port/" >/dev/null 2>&1; then
            print_success "$service_name is ready!"
            return 0
        fi
        
        if [ $attempt -eq 1 ]; then
            echo -n "Waiting"
        fi
        echo -n "."
        
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo
    print_error "$service_name failed to start within $(($max_attempts * 2)) seconds"
    return 1
}

# Function to start PostgreSQL
start_postgresql() {
    print_status "Checking PostgreSQL..."
    
    if command_exists systemctl; then
        if systemctl is-active --quiet postgresql; then
            print_success "PostgreSQL is already running"
        else
            print_status "Starting PostgreSQL..."
            sudo systemctl start postgresql
            if systemctl is-active --quiet postgresql; then
                print_success "PostgreSQL started successfully"
            else
                print_error "Failed to start PostgreSQL"
                return 1
            fi
        fi
    elif command_exists pg_ctl; then
        if pg_isready >/dev/null 2>&1; then
            print_success "PostgreSQL is already running"
        else
            print_status "Starting PostgreSQL..."
            pg_ctl start -D /usr/local/var/postgres
        fi
    else
        print_warning "Could not determine how to start PostgreSQL"
        print_warning "Please ensure PostgreSQL is running manually"
    fi
}

# Function to start Ollama
start_ollama() {
    print_status "Checking Ollama..."
    
    if port_in_use 11434; then
        print_success "Ollama is already running"
    else
        print_status "Starting Ollama..."
        if command_exists ollama; then
            # Start Ollama in background
            nohup ollama serve > /tmp/ollama.log 2>&1 &
            sleep 3
            
            if port_in_use 11434; then
                print_success "Ollama started successfully"
                
                # Check if llama3 model is available
                if ollama list | grep -q "llama3"; then
                    print_success "Llama3 model is available"
                else
                    print_warning "Llama3 model not found"
                    print_status "Pulling llama3 model (this may take a while)..."
                    ollama pull llama3
                    if [ $? -eq 0 ]; then
                        print_success "Llama3 model pulled successfully"
                    else
                        print_error "Failed to pull llama3 model"
                        return 1
                    fi
                fi
            else
                print_error "Failed to start Ollama"
                return 1
            fi
        else
            print_error "Ollama not found. Please install it first:"
            print_error "curl -fsSL https://ollama.ai/install.sh | sh"
            return 1
        fi
    fi
}

# Function to setup Python environment
setup_python_env() {
    print_status "Setting up Python environment..."
    
    # Check if we're in a virtual environment
    if [ -z "$VIRTUAL_ENV" ]; then
        if [ -d "venv" ]; then
            print_status "Activating virtual environment..."
            source venv/bin/activate
        else
            print_warning "No virtual environment found"
            print_status "Creating virtual environment..."
            python3 -m venv venv
            source venv/bin/activate
        fi
    fi
    
    print_success "Python environment ready"
}

# Function to install dependencies
install_dependencies() {
    print_status "Installing Python dependencies..."
    
    # Backend dependencies
    if [ -f "backend/requirements.txt" ]; then
        print_status "Installing backend dependencies..."
        pip install -r backend/requirements.txt
    fi
    
    # Frontend dependencies
    if [ -f "frontend/requirements.txt" ]; then
        print_status "Installing frontend dependencies..."
        pip install -r frontend/requirements.txt
    fi
    
    print_success "Dependencies installed"
}

# Function to setup databases
setup_databases() {
    print_status "Setting up databases..."
    
    if [ -f "scripts/setup_db.py" ]; then
        print_status "Setting up PostgreSQL database..."
        python scripts/setup_db.py
    fi
    
    if [ -f "scripts/setup_chromadb.py" ]; then
        print_status "Setting up ChromaDB..."
        python scripts/setup_chromadb.py
    fi
    
    print_success "Databases setup completed"
}

# Function to start backend
start_backend() {
    print_status "Starting FastAPI backend..."
    
    if port_in_use 8000; then
        print_warning "Port 8000 is already in use"
        print_status "Stopping existing service on port 8000..."
        if command_exists fuser; then
            fuser -k 8000/tcp 2>/dev/null || true
        fi
        sleep 2
    fi
    
    cd backend
    
    # Start backend in background
    nohup python -m app.main > /tmp/backend.log 2>&1 &
    backend_pid=$!
    echo $backend_pid > /tmp/backend.pid
    
    cd ..
    
    # Wait for backend to be ready
    if wait_for_service "localhost" "8000" "Backend API"; then
        print_success "Backend started successfully (PID: $backend_pid)"
        print_status "Backend logs: tail -f /tmp/backend.log"
    else
        print_error "Backend failed to start"
        return 1
    fi
}

# Function to start frontend
start_frontend() {
    print_status "Starting Streamlit frontend..."
    
    if port_in_use 8501; then
        print_warning "Port 8501 is already in use"
        print_status "Stopping existing service on port 8501..."
        if command_exists fuser; then
            fuser -k 8501/tcp 2>/dev/null || true
        fi
        sleep 2
    fi
    
    cd frontend
    
    # Start frontend in background
    nohup streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0 > /tmp/frontend.log 2>&1 &
    frontend_pid=$!
    echo $frontend_pid > /tmp/frontend.pid
    
    cd ..
    
    # Wait for frontend to be ready
    sleep 5
    if port_in_use 8501; then
        print_success "Frontend started successfully (PID: $frontend_pid)"
        print_status "Frontend logs: tail -f /tmp/frontend.log"
        print_success "Frontend URL: http://localhost:8501"
    else
        print_error "Frontend failed to start"
        return 1
    fi
}

# Function to show status
show_status() {
    print_status "Service Status:"
    echo "=================================="
    
    # PostgreSQL
    if command_exists pg_isready && pg_isready >/dev/null 2>&1; then
        print_success "✓ PostgreSQL: Running"
    else
        print_error "✗ PostgreSQL: Not running"
    fi
    
    # Ollama
    if port_in_use 11434; then
        print_success "✓ Ollama: Running (port 11434)"
    else
        print_error "✗ Ollama: Not running"
    fi
    
    # Backend
    if port_in_use 8000; then
        print_success "✓ Backend API: Running (port 8000)"
        print_status "  API Docs: http://localhost:8000/docs"
    else
        print_error "✗ Backend API: Not running"
    fi
    
    # Frontend
    if port_in_use 8501; then
        print_success "✓ Frontend: Running (port 8501)"
        print_status "  Dashboard: http://localhost:8501"
    else
        print_error "✗ Frontend: Not running"
    fi
    
    echo "=================================="
}

# Function to stop services
stop_services() {
    print_status "Stopping services..."
    
    # Stop frontend
    if [ -f "/tmp/frontend.pid" ]; then
        frontend_pid=$(cat /tmp/frontend.pid)
        if kill -0 $frontend_pid 2>/dev/null; then
            kill $frontend_pid
            print_success "Frontend stopped"
        fi
        rm -f /tmp/frontend.pid
    fi
    
    # Stop backend
    if [ -f "/tmp/backend.pid" ]; then
        backend_pid=$(cat /tmp/backend.pid)
        if kill -0 $backend_pid 2>/dev/null; then
            kill $backend_pid
            print_success "Backend stopped"
        fi
        rm -f /tmp/backend.pid
    fi
    
    # Kill any remaining processes on our ports
    if command_exists fuser; then
        fuser -k 8000/tcp 2>/dev/null || true
        fuser -k 8501/tcp 2>/dev/null || true
    fi
    
    print_success "Services stopped"
}

# Function to show help
show_help() {
    echo "Alert Monitoring MVP - Service Runner"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  start        Start all services (default)"
    echo "  stop         Stop all services"
    echo "  restart      Restart all services"
    echo "  status       Show service status"
    echo "  setup        Setup databases and dependencies"
    echo "  logs         Show service logs"
    echo "  help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                 # Start all services"
    echo "  $0 start           # Start all services"
    echo "  $0 stop            # Stop all services"
    echo "  $0 status          # Check service status"
    echo ""
}

# Function to show logs
show_logs() {
    print_status "Service logs (press Ctrl+C to exit):"
    echo "=================================="
    
    if [ -f "/tmp/backend.log" ] && [ -f "/tmp/frontend.log" ]; then
        tail -f /tmp/backend.log /tmp/frontend.log
    elif [ -f "/tmp/backend.log" ]; then
        tail -f /tmp/backend.log
    elif [ -f "/tmp/frontend.log" ]; then
        tail -f /tmp/frontend.log
    else
        print_warning "No log files found"
    fi
}

# Main function
main() {
    local command=${1:-start}
    
    echo "🚀 Alert Monitoring MVP - Service Runner"
    echo "========================================"
    
    case $command in
        "start")
            # Check prerequisites
            if ! command_exists python3; then
                print_error "Python 3 is required but not installed"
                exit 1
            fi
            
            if ! command_exists pip; then
                print_error "pip is required but not installed"
                exit 1
            fi
            
            # Setup and start services
            setup_python_env
            install_dependencies
            start_postgresql
            start_ollama
            setup_databases
            start_backend
            start_frontend
            
            echo ""
            print_success "🎉 All services started successfully!"
            echo ""
            show_status
            echo ""
            print_status "Useful commands:"
            print_status "  $0 status    # Check service status"
            print_status "  $0 logs      # View service logs"
            print_status "  $0 stop      # Stop all services"
            ;;
        
        "stop")
            stop_services
            ;;
        
        "restart")
            stop_services
            sleep 2
            main start
            ;;
        
        "status")
            show_status
            ;;
        
        "setup")
            setup_python_env
            install_dependencies
            start_postgresql
            start_ollama
            setup_databases
            print_success "Setup completed"
            ;;
        
        "logs")
            show_logs
            ;;
        
        "help"|"-h"|"--help")
            show_help
            ;;
        
        *)
            print_error "Unknown command: $command"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Trap Ctrl+C
trap 'echo; print_status "Caught Ctrl+C, stopping services..."; stop_services; exit 0' INT

# Run main function
main "$@"
