# GeckoTerminal Data Collector - Deployment Guide

This guide covers deployment of the GeckoTerminal Data Collector in various environments using Docker and Docker Compose.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Deployment Options](#deployment-options)
- [Environment-Specific Deployments](#environment-specific-deployments)
- [Monitoring and Observability](#monitoring-and-observability)
- [Backup and Restore](#backup-and-restore)
- [Troubleshooting](#troubleshooting)
- [Production Considerations](#production-considerations)

## Prerequisites

### System Requirements

- **Operating System**: Linux, macOS, or Windows
- **Docker**: Version 20.10 or later
- **Docker Compose**: Version 2.0 or later (or docker-compose v1.29+)
- **Memory**: Minimum 1GB RAM, recommended 2GB+
- **Storage**: Minimum 10GB free space for data and logs
- **Network**: Internet access for API calls to GeckoTerminal

### Software Dependencies

- Git (for cloning the repository)
- Python 3.11+ (for local development)

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd gecko-terminal-collector
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit configuration (see Configuration section)
nano .env
```

### 3. Deploy with Default Settings

**Linux/macOS:**
```bash
./scripts/deploy.sh deploy
```

**Windows (PowerShell):**
```powershell
.\scripts\deploy.ps1 deploy
```

### 4. Check Status

```bash
# Linux/macOS
./scripts/deploy.sh status

# Windows
.\scripts\deploy.ps1 status
```

## Configuration

### Environment Variables

The application uses environment variables for configuration. Key variables include:

#### Database Configuration
```bash
GECKO_DB_URL=sqlite:///app/data/gecko_data.db  # Database connection URL
GECKO_DB_POOL_SIZE=10                          # Connection pool size
GECKO_DB_ECHO=false                            # Enable SQL query logging
```

#### API Configuration
```bash
GECKO_API_TIMEOUT=30                           # API request timeout (seconds)
GECKO_API_MAX_CONCURRENT=5                     # Max concurrent API requests
GECKO_API_RATE_LIMIT_DELAY=1.0                # Delay between requests (seconds)
```

#### Collection Configuration
```bash
GECKO_DEX_TARGETS=heaven,pumpswap              # Target DEXes to monitor
GECKO_DEX_NETWORK=solana                       # Blockchain network
GECKO_MIN_TRADE_VOLUME=100                     # Minimum trade volume (USD)
```

#### Collection Intervals
```bash
GECKO_TOP_POOLS_INTERVAL=1h                    # Top pools collection interval
GECKO_OHLCV_INTERVAL=1h                        # OHLCV data collection interval
GECKO_TRADE_INTERVAL=30m                       # Trade data collection interval
GECKO_WATCHLIST_INTERVAL=1h                    # Watchlist processing interval
```

### Configuration Files

#### Main Configuration (`config.yaml`)

```yaml
dexes:
  targets: ["heaven", "pumpswap"]
  network: "solana"

intervals:
  top_pools_monitoring: "1h"
  ohlcv_collection: "1h"
  trade_collection: "30m"
  watchlist_check: "1h"

database:
  url: "sqlite:///app/data/gecko_data.db"
  pool_size: 10
  echo: false

# ... additional configuration
```

#### Watchlist (`watchlist.csv`)

```csv
pool_id,symbol,name,network_address
solana_7bqJG2ZdMKbEkgSmfuqNVBvqEvWavgL8UEo33ZqdL3NP,TOKEN1,Token One,5LKHMd2rMSRaG9y4iHwSLRtrJ3dCrJ2CytvBeak8pump
# Add more tokens as needed
```

## Deployment Options

### Option 1: SQLite (Default)

Suitable for development and small-scale deployments:

```bash
# Uses SQLite database stored in Docker volume
./scripts/deploy.sh deploy
```

### Option 2: PostgreSQL

Recommended for production deployments:

```bash
# Set PostgreSQL password
export POSTGRES_PASSWORD=your_secure_password

# Deploy with PostgreSQL
./scripts/deploy.sh deploy --with-postgres
```

### Option 3: Full Stack with Monitoring

Complete deployment with monitoring and caching:

```bash
export POSTGRES_PASSWORD=your_secure_password
export GRAFANA_PASSWORD=your_grafana_password

./scripts/deploy.sh deploy --with-postgres --with-redis --with-monitoring
```

## Environment-Specific Deployments

### Development Environment

```bash
# Use development configuration
./scripts/deploy.sh -e development deploy

# Or with PowerShell
.\scripts\deploy.ps1 -Environment development deploy
```

Development environment features:
- More verbose logging (DEBUG level)
- Shorter collection intervals for testing
- Lower resource limits
- SQLite database for simplicity

### Production Environment

```bash
# Use production configuration
./scripts/deploy.sh -e production deploy

# Or with PowerShell
.\scripts\deploy.ps1 -Environment production deploy
```

Production environment features:
- PostgreSQL database
- Optimized resource allocation
- Monitoring and alerting
- Backup automation
- Security hardening

### Staging Environment

Create `.env.staging` with staging-specific configuration:

```bash
./scripts/deploy.sh -e staging deploy
```

## Monitoring and Observability

### Health Checks

```bash
# Check application health
./scripts/deploy.sh health

# View detailed status
./scripts/deploy.sh status
```

### Logs

```bash
# View recent logs
./scripts/deploy.sh logs

# Follow logs in real-time
./scripts/deploy.sh logs --follow

# View specific service logs
docker-compose logs -f gecko-collector
```

### Metrics and Monitoring

When deployed with monitoring (`--with-monitoring`):

- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Application Health**: http://localhost:8080/health

### Monitoring Stack Components

1. **Prometheus**: Metrics collection and storage
2. **Grafana**: Visualization and dashboards
3. **cAdvisor**: Container metrics (optional)
4. **Node Exporter**: System metrics (optional)

## Backup and Restore

### Creating Backups

```bash
# Create backup
./scripts/deploy.sh backup /path/to/backup/directory

# Or using CLI directly
docker exec gecko-collector python -m gecko_terminal_collector.cli backup /app/backups/backup-$(date +%Y%m%d)
```

### Restoring from Backup

```bash
# Restore from backup
./scripts/deploy.sh restore /path/to/backup/directory

# Or using CLI directly
docker exec gecko-collector python -m gecko_terminal_collector.cli restore /app/backups/backup-20240101 --verify
```

### Automated Backups

Add to crontab for automated backups:

```bash
# Daily backup at 2 AM
0 2 * * * /path/to/gecko-terminal-collector/scripts/deploy.sh backup /backups/gecko-$(date +\%Y\%m\%d)
```

## Troubleshooting

### Common Issues

#### Container Won't Start

```bash
# Check container logs
docker-compose logs gecko-collector

# Check system resources
docker system df
docker system prune  # Clean up if needed
```

#### Database Connection Issues

```bash
# For PostgreSQL issues
docker-compose logs postgres

# Check database connectivity
docker exec gecko-collector python -m gecko_terminal_collector.cli validate --check-db
```

#### API Connection Issues

```bash
# Test API connectivity
docker exec gecko-collector python -m gecko_terminal_collector.cli validate --check-api

# Check network connectivity
docker exec gecko-collector ping api.geckoterminal.com
```

#### High Memory Usage

```bash
# Check resource usage
docker stats

# Adjust memory limits in docker-compose.yml
# Or set environment variables:
export MEMORY_LIMIT=2G
export MEMORY_RESERVATION=1G
```

### Debug Mode

Enable debug logging:

```bash
# Set debug level
export GECKO_LOG_LEVEL=DEBUG

# Restart services
./scripts/deploy.sh restart
```

### Performance Issues

1. **Check system resources**: `docker stats`
2. **Review collection intervals**: Increase if too frequent
3. **Monitor API rate limits**: Check logs for rate limit errors
4. **Database performance**: Consider PostgreSQL for better performance

## Production Considerations

### Security

1. **Use strong passwords** for database and monitoring services
2. **Enable SSL/TLS** for external connections
3. **Restrict network access** using firewalls
4. **Regular security updates** for base images
5. **Use secrets management** for sensitive configuration

### Scalability

1. **Horizontal scaling**: Run multiple collector instances
2. **Database optimization**: Use PostgreSQL with proper indexing
3. **Caching**: Enable Redis for API response caching
4. **Load balancing**: Distribute API requests across instances

### Reliability

1. **Health checks**: Monitor application health
2. **Restart policies**: Configure automatic restart on failure
3. **Data backup**: Implement regular backup strategy
4. **Monitoring**: Set up alerts for critical issues
5. **Resource limits**: Prevent resource exhaustion

### Maintenance

1. **Log rotation**: Configure log rotation to prevent disk space issues
2. **Data cleanup**: Regularly clean old data based on retention policy
3. **Image updates**: Keep Docker images updated
4. **Dependency updates**: Regular security updates

### Example Production docker-compose.yml

```yaml
version: '3.8'

services:
  gecko-collector:
    image: gecko-terminal-collector:latest
    restart: unless-stopped
    environment:
      - GECKO_DB_URL=postgresql://gecko:${POSTGRES_PASSWORD}@postgres:5432/gecko_data
      - GECKO_LOG_LEVEL=INFO
    volumes:
      - gecko_data:/app/data
      - gecko_logs:/app/logs
      - gecko_backups:/app/backups
    depends_on:
      - postgres
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '2.0'
        reservations:
          memory: 1G
          cpus: '1.0'
    healthcheck:
      test: ["CMD", "python", "-m", "gecko_terminal_collector.cli", "health-check"]
      interval: 30s
      timeout: 10s
      retries: 3

  postgres:
    image: postgres:15-alpine
    restart: unless-stopped
    environment:
      - POSTGRES_DB=gecko_data
      - POSTGRES_USER=gecko
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '1.0'

volumes:
  gecko_data:
  gecko_logs:
  gecko_backups:
  postgres_data:
```

## Support

For issues and questions:

1. Check the [troubleshooting section](#troubleshooting)
2. Review application logs
3. Check system resources and connectivity
4. Consult the main README.md for additional information

## License

This deployment guide is part of the GeckoTerminal Data Collector project.