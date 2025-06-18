#!/bin/bash

# SMTP Email Server Launcher Script
# 
# This script manages the startup and shutdown of all SMTP email server components:
# - Redis server (for message queuing)
# - SMTP handler (for receiving emails)
# - Database worker (for email storage)
# - Web UI/API server (for email management)
#
# Usage: ./run.sh [start|stop|restart|status]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "SMTP Email Server Management"
echo "============================"

# Activate virtual environment if available
if [ -d ".venv" ]; then
    echo "Activating Python virtual environment..."
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo "Activating Python virtual environment..."
    source venv/bin/activate
else
    echo "WARNING: No virtual environment found, using system Python"
fi

# Load environment configuration
if [ -f ".env" ]; then
    echo "Loading configuration from .env file..."
    source .env
    export $(grep -v '^#' .env | grep -v '^$' | cut -d= -f1)
else
    echo "WARNING: No .env file found, using default settings..."
fi

# Set defaults if not in .env
export EMAIL_ENCRYPTION_KEY=${EMAIL_ENCRYPTION_KEY:-"u8lr09g1MClOA1VzIbPZbgTtU4vdi4DQh-OHSzVtAmg="}
export EMAIL_UI_USERS=${EMAIL_UI_USERS:-'admin:$2b$12$lABwphGhtU6s0PtCyMr4WOlS6F8OeemfXhUhpC2Oaawm2SUkYo8Pi:VDHEAPMAXDD2PQOGPZH4FVXRKDNHJ6QH'}
export SMTP_PORT=${SMTP_PORT:-587}
export WEB_PORT=${WEB_PORT:-8001}
export WEB_HOST=${WEB_HOST:-"0.0.0.0"}

# Create directories
mkdir -p data logs

# Function to check if Redis is available
check_redis_available() {
    if command -v redis-server >/dev/null 2>&1; then
        return 0  # Redis is available
    else
        return 1  # Redis is not available
    fi
}

# Function to check if Docker is available
check_docker_available() {
    if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
        return 0  # Docker is available
    else
        return 1  # Docker is not available
    fi
}

# Function to start Redis locally
start_local_redis() {
    echo "Starting local Redis Server..."
    nohup redis-server redis.conf > logs/redis.log 2>&1 &
    REDIS_PID=$!
    echo $REDIS_PID > logs/redis.pid
    sleep 3
    
    if kill -0 $REDIS_PID 2>/dev/null; then
        echo "SUCCESS: Local Redis Server started (PID: $REDIS_PID)"
        return 0
    else
        echo "ERROR: Failed to start local Redis Server"
        return 1
    fi
}

# Function to check if Redis is accessible on port 6379
check_redis_connection() {
    # Try multiple methods to check Redis connectivity
    if command -v nc >/dev/null 2>&1; then
        # Use netcat if available
        if nc -z localhost 6379 2>/dev/null; then
            return 0
        fi
    fi
    
    # Fallback to TCP connection test
    if timeout 3 bash -c '</dev/tcp/localhost/6379' 2>/dev/null; then
        return 0
    fi
    
    return 1  # Redis is not accessible
}

# Function to start Redis via Docker
start_docker_redis() {
    # First check if Redis is already accessible
    if check_redis_connection; then
        echo "SUCCESS: Redis already accessible on port 6379"
        echo "docker:existing" > logs/redis.pid  # Mark as existing Docker Redis
        return 0
    fi
    
    echo "Starting Redis via Docker..."
    docker run -d --name redis-smtp -p 6379:6379 redis:7-alpine > /dev/null 2>&1
    sleep 3
    
    if docker ps --filter "name=redis-smtp" --filter "status=running" | grep -q redis-smtp; then
        echo "SUCCESS: Docker Redis started"
        echo "docker:redis-smtp" > logs/redis.pid  # Mark as Docker Redis
        return 0
    else
        echo "ERROR: Failed to start Docker Redis"
        return 1
    fi
}

# Function to stop Docker Redis
stop_docker_redis() {
    # Stop and remove any existing redis-smtp container (running or stopped)
    if docker ps -a --filter "name=redis-smtp" | grep -q redis-smtp; then
        docker stop redis-smtp > /dev/null 2>&1
        docker rm redis-smtp > /dev/null 2>&1
        echo "Docker Redis cleaned up"
    fi
}

case "${1:-start}" in
    start)
        echo ""
        echo "Detecting Redis setup..."
        
        # Kill any existing processes
        pkill -f "redis-server" 2>/dev/null || true
        pkill -f "python MailHandler.py" 2>/dev/null || true
        pkill -f "uvicorn email_ui_api" 2>/dev/null || true
        pkill -f "python redis_to_db_worker.py" 2>/dev/null || true
        stop_docker_redis
        sleep 2
        
        # Determine Redis strategy
        REDIS_STARTED=false
        
        if check_redis_available; then
            echo "✅ Redis found locally, using local Redis server"
            if start_local_redis; then
                REDIS_STARTED=true
            fi
        elif check_docker_available; then
            echo "⚠️  Redis not found locally, using Docker Redis"
            if start_docker_redis; then
                REDIS_STARTED=true
            fi
        else
            echo "❌ Neither Redis nor Docker available!"
            echo ""
            echo "Please install one of the following:"
            echo "1. Install Redis locally: brew install redis"
            echo "2. Install Docker Desktop for Mac"
            echo "3. Use the Docker container (includes embedded Redis): cd docker && ./build.sh"
            exit 1
        fi
        
        if [ "$REDIS_STARTED" = false ]; then
            echo "❌ Failed to start Redis. Cannot continue."
            exit 1
        fi
        
        # Start SMTP Server
        echo "Starting SMTP Server on port $SMTP_PORT..."
        nohup python MailHandler.py > logs/smtp.log 2>&1 &
        SMTP_PID=$!
        echo $SMTP_PID > logs/smtp.pid
        sleep 2
        
        if kill -0 $SMTP_PID 2>/dev/null; then
            echo "SUCCESS: SMTP Server started (PID: $SMTP_PID)"
        else
            echo "ERROR: Failed to start SMTP Server"
            exit 1
        fi
        
        # Start Web UI
        echo "Starting Web UI/API on port $WEB_PORT..."
        nohup uvicorn email_ui_api:app --host $WEB_HOST --port $WEB_PORT --log-config logging.yaml > logs/web.log 2>&1 &
        WEB_PID=$!
        echo $WEB_PID > logs/web.pid
        sleep 3
        
        if kill -0 $WEB_PID 2>/dev/null; then
            echo "SUCCESS: Web UI/API started (PID: $WEB_PID)"
        else
            echo "ERROR: Failed to start Web UI"
            exit 1
        fi
        
        # Start Redis Worker
        echo "Starting Redis Worker..."
        nohup python redis_to_db_worker.py > logs/worker.log 2>&1 &
        WORKER_PID=$!
        echo $WORKER_PID > logs/worker.pid
        sleep 2
        
        if kill -0 $WORKER_PID 2>/dev/null; then
            echo "SUCCESS: Redis Worker started (PID: $WORKER_PID)"
        else
            echo "ERROR: Failed to start Redis Worker"
            exit 1
        fi
        
        echo ""
        echo "All services started successfully!"
        echo ""
        echo "SMTP Server: localhost:$SMTP_PORT"
        echo "Web UI: http://localhost:$WEB_PORT"
        echo "API Docs: http://localhost:$WEB_PORT/docs"
        echo ""
        echo "Use '$0 stop' to stop services, '$0 logs' to view logs"
        echo "Use '$0 totp' to generate TOTP code for login"
        
        # Keep container running by monitoring processes
        echo ""
        echo "Monitoring services... (Press Ctrl+C to stop)"
        
        trap 'echo "Received shutdown signal, stopping services..."; ./run.sh stop; exit 0' SIGTERM SIGINT
        
        while true; do
            # Check if all services are still running
            if [ -f "logs/redis.pid" ] && [ -f "logs/smtp.pid" ] && [ -f "logs/web.pid" ] && [ -f "logs/worker.pid" ]; then
                REDIS_PID=$(cat logs/redis.pid)
                SMTP_PID=$(cat logs/smtp.pid)
                WEB_PID=$(cat logs/web.pid)
                WORKER_PID=$(cat logs/worker.pid)
                
                # Check if any process has died
                if [ -f "logs/redis.pid" ]; then
                    REDIS_PID=$(cat logs/redis.pid)
                    if [[ "$REDIS_PID" == docker:* ]]; then
                        # Check if Redis is still accessible (Docker Redis)
                        if ! check_redis_connection; then
                            echo "ERROR: Docker Redis connection lost, attempting restart..."
                            if start_docker_redis; then
                                echo "Docker Redis connection restored"
                            fi
                        fi
                    else
                        # Check local Redis
                        if ! kill -0 $REDIS_PID 2>/dev/null; then
                            echo "ERROR: Local Redis Server process died, restarting..."
                            if start_local_redis; then
                                echo "Local Redis restarted successfully"
                            fi
                        fi
                    fi
                fi
                
                if ! kill -0 $SMTP_PID 2>/dev/null; then
                    echo "ERROR: SMTP Server process died, restarting..."
                    nohup python MailHandler.py > logs/smtp.log 2>&1 &
                    SMTP_PID=$!
                    echo $SMTP_PID > logs/smtp.pid
                fi
                
                if ! kill -0 $WEB_PID 2>/dev/null; then
                    echo "ERROR: Web UI process died, restarting..."
                    nohup uvicorn email_ui_api:app --host $WEB_HOST --port $WEB_PORT --log-config logging.yaml > logs/web.log 2>&1 &
                    WEB_PID=$!
                    echo $WEB_PID > logs/web.pid
                fi
                
                if ! kill -0 $WORKER_PID 2>/dev/null; then
                    echo "ERROR: Redis Worker process died, restarting..."
                    nohup python redis_to_db_worker.py > logs/worker.log 2>&1 &
                    WORKER_PID=$!
                    echo $WORKER_PID > logs/worker.pid
                fi
            fi
            
            sleep 30  # Check every 30 seconds
        done
        ;;
    
    stop)
        echo "Stopping services..."
        
        if [ -f "logs/redis.pid" ]; then
            REDIS_PID=$(cat logs/redis.pid)
            
            # Check if it's Docker Redis or local Redis
            if [[ "$REDIS_PID" == docker:* ]]; then
                if [ "$REDIS_PID" = "docker:redis-smtp" ]; then
                    stop_docker_redis
                else
                    echo "Note: Using existing Docker Redis container (not stopped)"
                fi
            else
                if kill -0 $REDIS_PID 2>/dev/null; then
                    kill $REDIS_PID
                    echo "Local Redis Server stopped"
                fi
            fi
            rm -f logs/redis.pid
        fi
        
        if [ -f "logs/smtp.pid" ]; then
            SMTP_PID=$(cat logs/smtp.pid)
            if kill -0 $SMTP_PID 2>/dev/null; then
                kill $SMTP_PID
                echo "SMTP Server stopped"
            fi
            rm -f logs/smtp.pid
        fi
        
        if [ -f "logs/web.pid" ]; then
            WEB_PID=$(cat logs/web.pid)
            if kill -0 $WEB_PID 2>/dev/null; then
                kill $WEB_PID
                echo "Web UI stopped"
            fi
            rm -f logs/web.pid
        fi
        
        if [ -f "logs/worker.pid" ]; then
            WORKER_PID=$(cat logs/worker.pid)
            if kill -0 $WORKER_PID 2>/dev/null; then
                kill $WORKER_PID
                echo "Redis Worker stopped"
            fi
            rm -f logs/worker.pid
        fi
        
        # Also kill by process name as backup
        pkill -f "redis-server" 2>/dev/null || true
        pkill -f "python MailHandler.py" 2>/dev/null || true
        pkill -f "uvicorn email_ui_api" 2>/dev/null || true
        pkill -f "python redis_to_db_worker.py" 2>/dev/null || true
        stop_docker_redis  # Also stop Docker Redis if running
        
        echo "All services stopped"
        ;;
    
    status)
        echo "Service Status:"
        echo "=============="
        
        if [ -f "logs/redis.pid" ]; then
            REDIS_PID=$(cat logs/redis.pid)
            
            if [[ "$REDIS_PID" == docker:* ]]; then
                if check_redis_connection; then
                    if [ "$REDIS_PID" = "docker:redis-smtp" ]; then
                        echo "Redis Server: Running (Docker: redis-smtp)"
                    else
                        echo "Redis Server: Running (Docker: existing container)"
                    fi
                else
                    echo "Redis Server: Not accessible (Docker connection lost)"
                    rm -f logs/redis.pid
                fi
            else
                if kill -0 $REDIS_PID 2>/dev/null; then
                    echo "Redis Server: Running (Local PID: $REDIS_PID)"
                else
                    echo "Redis Server: Not running"
                    rm -f logs/redis.pid
                fi
            fi
        else
            echo "Redis Server: Not running"
        fi
        
        if [ -f "logs/smtp.pid" ]; then
            SMTP_PID=$(cat logs/smtp.pid)
            if kill -0 $SMTP_PID 2>/dev/null; then
                echo "SMTP Server: Running (PID: $SMTP_PID)"
            else
                echo "SMTP Server: Not running"
                rm -f logs/smtp.pid
            fi
        else
            echo "SMTP Server: Not running"
        fi
        
        if [ -f "logs/web.pid" ]; then
            WEB_PID=$(cat logs/web.pid)
            if kill -0 $WEB_PID 2>/dev/null; then
                echo "Web UI: Running (PID: $WEB_PID)"
            else
                echo "Web UI: Not running"
                rm -f logs/web.pid
            fi
        else
            echo "Web UI: Not running"
        fi
        
        if [ -f "logs/worker.pid" ]; then
            WORKER_PID=$(cat logs/worker.pid)
            if kill -0 $WORKER_PID 2>/dev/null; then
                echo "Redis Worker: Running (PID: $WORKER_PID)"
            else
                echo "Redis Worker: Not running"
                rm -f logs/worker.pid
            fi
        else
            echo "Redis Worker: Not running"
        fi
        ;;
    
    logs)
        echo "Recent Logs:"
        echo "==========="
        
        if [ -f "logs/smtp.log" ]; then
            echo ""
            echo "--- SMTP Server Log ---"
            tail -n 10 logs/smtp.log
        fi
        
        if [ -f "logs/web.log" ]; then
            echo ""
            echo "--- Web UI Log ---"
            tail -n 10 logs/web.log
        fi
        
        if [ -f "logs/worker.log" ]; then
            echo ""
            echo "--- Redis Worker Log ---"
            tail -n 10 logs/worker.log
        fi
        ;;
    
    test)
        echo "Sending test email..."
        python testing/send_test_email.py
        ;;
    
    totp)
        echo "Current TOTP Code:"
        python -c "import pyotp; print('TOTP Code:', pyotp.TOTP('VDHEAPMAXDD2PQOGPZH4FVXRKDNHJ6QH').now())"
        ;;
    
    *)
        echo "Usage: $0 {start|stop|status|logs|test|totp}"
        echo ""
        echo "Commands:"
        echo "  start   - Start SMTP server and Web UI"
        echo "  stop    - Stop all services"
        echo "  status  - Show service status"
        echo "  logs    - Show recent logs"
        echo "  test    - Send a test email"
        echo "  totp    - Generate current TOTP code"
        ;;
esac
