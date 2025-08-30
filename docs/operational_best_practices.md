# Operational Best Practices

This guide provides best practices for deploying, operating, and maintaining the GeckoTerminal Data Collector system in production environments.

## Table of Contents

- [Production Deployment](#production-deployment)
- [Security Best Practices](#security-best-practices)
- [Performance Optimization](#performance-optimization)
- [Monitoring and Alerting](#monitoring-and-alerting)
- [Backup and Recovery](#backup-and-recovery)
- [Maintenance Procedures](#maintenance-procedures)
- [Scaling Strategies](#scaling-strategies)
- [Disaster Recovery](#disaster-recovery)
- [Compliance and Governance](#compliance-and-governance)

## Production Deployment

### Infrastructure Requirements

#### Minimum Production Requirements
```yaml
# Recommended server specifications
CPU: 4 cores (2.4GHz+)
RAM: 8GB
Storage: 100GB SSD
Network: 100Mbps with low latency
OS: Ubuntu 20.04 LTS or CentOS 8+
```

#### Recommended Production Setup
```yaml
# High-availability setup
CPU: 8 cores (3.0GHz+)
RAM: 16GB
Storage: 500GB NVMe SSD
Network: 1Gbps with redundancy
Database: Separate PostgreSQL server
Load Balancer: For multiple instances
Monitoring: Dedicated monitoring stack
```

### Environment Configuration

#### Production Configuration Template
```yaml
# config-production.yaml
dexes:
  targets: ["heaven", "pumpswap"]
  network: "solana"

intervals:
  top_pools_monitoring: "1h"
  ohlcv_collection: "1h"
  trade_collection: "30m"
  watchlist_check: "1h"

thresholds:
  min_trade_volume_usd: 1000
  max_retries: 5
  rate_limit_delay: 1.5
  max_concurrent_requests: 8
  circuit_breaker_threshold: 10
  circuit_breaker_timeout: 300

database:
  url: "${DATABASE_URL}"
  pool_size: 50
  max_overflow: 100
  pool_timeout: 30
  pool_recycle: 3600
  echo: false

api:
  timeout: 60
  max_concurrent: 8
  retry_backoff_factor: 2.0

logging:
  level: "INFO"
  format: "structured"
  file_path: "/var/log/gecko-collector/app.log"
  max_file_size: "100MB"
  backup_count: 10
  console_output: false

monitoring:
  enabled: true
  metrics_port: 8080
  health_check_port: 8081
```

#### Environment Variables
```bash
# /etc/environment or systemd service file
DATABASE_URL="postgresql://gecko_user:${DB_PASSWORD}@db-server:5432/gecko_terminal_data"
GECKO_LOG_LEVEL="INFO"
GECKO_API_TIMEOUT=60
GECKO_MONITORING_ENABLED=true
```

### Deployment Methods

#### Docker Deployment
```dockerfile
# Dockerfile.production
FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create application user
RUN useradd --create-home --shell /bin/bash gecko

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .
RUN pip install -e .

# Set ownership
RUN chown -R gecko:gecko /app

# Switch to application user
USER gecko

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -m gecko_terminal_collector.cli health-check || exit 1

# Start application
CMD ["python", "-m", "gecko_terminal_collector.cli", "start"]
```

```yaml
# docker-compose.production.yml
version: '3.8'

services:
  gecko-collector:
    build:
      context: .
      dockerfile: Dockerfile.production
    restart: unless-stopped
    environment:
      - DATABASE_URL=postgresql://gecko_user:${DB_PASSWORD}@postgres:5432/gecko_terminal_data
    volumes:
      - ./config-production.yaml:/app/config.yaml:ro
      - ./watchlist.csv:/app/watchlist.csv:ro
      - logs:/var/log/gecko-collector
      - data:/app/data
    depends_on:
      - postgres
    networks:
      - gecko-network

  postgres:
    image: postgres:13
    restart: unless-stopped
    environment:
      - POSTGRES_DB=gecko_terminal_data
      - POSTGRES_USER=gecko_user
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - gecko-network

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - gecko-collector
    networks:
      - gecko-network

volumes:
  postgres_data:
  logs:
  data:

networks:
  gecko-network:
    driver: bridge
```

#### Systemd Service
```ini
# /etc/systemd/system/gecko-collector.service
[Unit]
Description=GeckoTerminal Data Collector
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=gecko
Group=gecko
WorkingDirectory=/opt/gecko-terminal-collector
Environment=PATH=/opt/gecko-terminal-collector/venv/bin
ExecStart=/opt/gecko-terminal-collector/venv/bin/python -m gecko_terminal_collector.cli start
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=gecko-collector

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/gecko-terminal-collector/data /var/log/gecko-collector

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable gecko-collector
sudo systemctl start gecko-collector
sudo systemctl status gecko-collector
```

## Security Best Practices

### Access Control

#### User Management
```bash
# Create dedicated user
sudo useradd --system --create-home --shell /bin/bash gecko
sudo usermod -aG docker gecko  # If using Docker

# Set proper file permissions
sudo chown -R gecko:gecko /opt/gecko-terminal-collector
sudo chmod 750 /opt/gecko-terminal-collector
sudo chmod 640 /opt/gecko-terminal-collector/config.yaml
```

#### Database Security
```sql
-- Create dedicated database user with minimal privileges
CREATE USER gecko_user WITH PASSWORD 'strong_random_password';
CREATE DATABASE gecko_terminal_data OWNER gecko_user;

-- Grant only necessary privileges
GRANT CONNECT ON DATABASE gecko_terminal_data TO gecko_user;
GRANT USAGE ON SCHEMA public TO gecko_user;
GRANT CREATE ON SCHEMA public TO gecko_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO gecko_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO gecko_user;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO gecko_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO gecko_user;
```

### Network Security

#### Firewall Configuration
```bash
# UFW (Ubuntu)
sudo ufw enable
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 8080/tcp  # Metrics port
sudo ufw allow 8081/tcp  # Health check port
sudo ufw allow from 10.0.0.0/8 to any port 5432  # Database (internal network only)

# iptables (alternative)
sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 8080 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 8081 -j ACCEPT
sudo iptables -A INPUT -j DROP
```

#### SSL/TLS Configuration
```nginx
# nginx.conf
server {
    listen 443 ssl http2;
    server_name gecko-collector.example.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;

    location /health {
        proxy_pass http://localhost:8081/health;
    }

    location /metrics {
        proxy_pass http://localhost:8080/metrics;
        allow 10.0.0.0/8;  # Monitoring network only
        deny all;
    }
}
```

### Secrets Management

#### Environment Variables
```bash
# Use systemd environment files
# /etc/gecko-collector/environment
DATABASE_PASSWORD=secure_random_password
API_KEY=api_key_if_needed

# Set proper permissions
sudo chmod 600 /etc/gecko-collector/environment
sudo chown root:gecko /etc/gecko-collector/environment
```

#### External Secrets Management
```yaml
# Using HashiCorp Vault
secrets:
  vault:
    url: "https://vault.example.com"
    role: "gecko-collector"
    secrets:
      - path: "secret/gecko/database"
        key: "password"
        env: "DATABASE_PASSWORD"
```

## Performance Optimization

### Database Optimization

#### PostgreSQL Configuration
```postgresql
# postgresql.conf optimizations
shared_buffers = 2GB                    # 25% of RAM
effective_cache_size = 6GB              # 75% of RAM
maintenance_work_mem = 512MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1                  # For SSD storage
effective_io_concurrency = 200          # For SSD storage

# Connection settings
max_connections = 200
shared_preload_libraries = 'pg_stat_statements'
```

#### Index Optimization
```sql
-- Create performance indexes
CREATE INDEX CONCURRENTLY idx_ohlcv_pool_timeframe_timestamp 
ON ohlcv_data (pool_id, timeframe, timestamp);

CREATE INDEX CONCURRENTLY idx_trades_pool_timestamp 
ON trades (pool_id, block_timestamp);

CREATE INDEX CONCURRENTLY idx_pools_dex_reserve 
ON pools (dex_id, reserve_usd DESC);

-- Analyze tables regularly
ANALYZE ohlcv_data;
ANALYZE trades;
ANALYZE pools;
```

### Application Optimization

#### Connection Pooling
```yaml
# config.yaml
database:
  pool_size: 50
  max_overflow: 100
  pool_timeout: 30
  pool_recycle: 3600
  pool_pre_ping: true
```

#### Async Optimization
```python
# Custom collector optimization
class OptimizedCollector(BaseDataCollector):
    async def collect_batch(self, items: List[str]) -> CollectionResult:
        """Optimized batch collection with semaphore."""
        semaphore = asyncio.Semaphore(self.config.max_concurrent)
        
        async def collect_item(item: str):
            async with semaphore:
                return await self._collect_single_item(item)
        
        # Process in batches to control memory usage
        batch_size = 100
        all_results = []
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            tasks = [collect_item(item) for item in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            all_results.extend(batch_results)
            
            # Small delay between batches
            if i + batch_size < len(items):
                await asyncio.sleep(0.1)
        
        return self._aggregate_results(all_results)
```

### System Optimization

#### OS-Level Optimizations
```bash
# Increase file descriptor limits
echo "gecko soft nofile 65536" >> /etc/security/limits.conf
echo "gecko hard nofile 65536" >> /etc/security/limits.conf

# Optimize network settings
echo "net.core.somaxconn = 65535" >> /etc/sysctl.conf
echo "net.ipv4.tcp_max_syn_backlog = 65535" >> /etc/sysctl.conf
echo "net.core.netdev_max_backlog = 5000" >> /etc/sysctl.conf

# Apply changes
sudo sysctl -p
```

#### Memory Management
```yaml
# config.yaml
system:
  memory_limit: "8GB"
  gc_threshold: 0.8
  batch_processing: true
  max_batch_size: 1000
```

## Monitoring and Alerting

### Metrics Collection

#### Prometheus Integration
```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'gecko-collector'
    static_configs:
      - targets: ['localhost:8080']
    scrape_interval: 30s
    metrics_path: /metrics
```

#### Custom Metrics
```python
# monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Collection metrics
collection_total = Counter('gecko_collections_total', 'Total collections', ['collector_type', 'status'])
collection_duration = Histogram('gecko_collection_duration_seconds', 'Collection duration', ['collector_type'])
collection_records = Gauge('gecko_collection_records', 'Records collected', ['collector_type'])

# API metrics
api_requests_total = Counter('gecko_api_requests_total', 'Total API requests', ['endpoint', 'status'])
api_request_duration = Histogram('gecko_api_request_duration_seconds', 'API request duration', ['endpoint'])

# Database metrics
db_connections = Gauge('gecko_db_connections', 'Database connections')
db_query_duration = Histogram('gecko_db_query_duration_seconds', 'Database query duration', ['operation'])
```

### Alerting Rules

#### Prometheus Alerting Rules
```yaml
# alerts.yml
groups:
  - name: gecko-collector
    rules:
      - alert: CollectionFailure
        expr: increase(gecko_collections_total{status="failed"}[5m]) > 3
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Multiple collection failures detected"
          description: "{{ $value }} collections have failed in the last 5 minutes"

      - alert: HighAPIErrorRate
        expr: rate(gecko_api_requests_total{status=~"4..|5.."}[5m]) > 0.1
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "High API error rate"
          description: "API error rate is {{ $value }} errors per second"

      - alert: DatabaseConnectionIssue
        expr: gecko_db_connections < 1
        for: 30s
        labels:
          severity: critical
        annotations:
          summary: "Database connection issue"
          description: "No active database connections"

      - alert: HighMemoryUsage
        expr: process_resident_memory_bytes / 1024 / 1024 / 1024 > 8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage"
          description: "Memory usage is {{ $value }}GB"
```

### Log Aggregation

#### ELK Stack Configuration
```yaml
# filebeat.yml
filebeat.inputs:
- type: log
  enabled: true
  paths:
    - /var/log/gecko-collector/*.log
  fields:
    service: gecko-collector
  fields_under_root: true

output.elasticsearch:
  hosts: ["elasticsearch:9200"]
  index: "gecko-collector-%{+yyyy.MM.dd}"

processors:
  - add_host_metadata:
      when.not.contains.tags: forwarded
```

```json
# Elasticsearch index template
{
  "index_patterns": ["gecko-collector-*"],
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 1
  },
  "mappings": {
    "properties": {
      "@timestamp": {"type": "date"},
      "level": {"type": "keyword"},
      "message": {"type": "text"},
      "service": {"type": "keyword"},
      "collector_type": {"type": "keyword"},
      "pool_id": {"type": "keyword"}
    }
  }
}
```

## Backup and Recovery

### Backup Strategy

#### Database Backups
```bash
#!/bin/bash
# backup-database.sh

BACKUP_DIR="/var/backups/gecko-collector"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="gecko_terminal_data"
DB_USER="gecko_user"

# Create backup directory
mkdir -p $BACKUP_DIR

# Full database backup
pg_dump -h localhost -U $DB_USER -d $DB_NAME -f "$BACKUP_DIR/full_backup_$DATE.sql"

# Compress backup
gzip "$BACKUP_DIR/full_backup_$DATE.sql"

# Keep only last 30 days of backups
find $BACKUP_DIR -name "full_backup_*.sql.gz" -mtime +30 -delete

# Upload to S3 (optional)
aws s3 cp "$BACKUP_DIR/full_backup_$DATE.sql.gz" s3://gecko-backups/database/
```

#### Configuration Backups
```bash
#!/bin/bash
# backup-config.sh

BACKUP_DIR="/var/backups/gecko-collector/config"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup configuration files
tar -czf "$BACKUP_DIR/config_backup_$DATE.tar.gz" \
  /opt/gecko-terminal-collector/config.yaml \
  /opt/gecko-terminal-collector/watchlist.csv \
  /etc/systemd/system/gecko-collector.service

# Keep only last 90 days
find $BACKUP_DIR -name "config_backup_*.tar.gz" -mtime +90 -delete
```

#### Automated Backup Schedule
```bash
# Add to crontab
0 2 * * * /opt/gecko-terminal-collector/scripts/backup-database.sh
0 3 * * 0 /opt/gecko-terminal-collector/scripts/backup-config.sh
```

### Recovery Procedures

#### Database Recovery
```bash
#!/bin/bash
# restore-database.sh

BACKUP_FILE="$1"
DB_NAME="gecko_terminal_data"
DB_USER="gecko_user"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file>"
    exit 1
fi

# Stop application
sudo systemctl stop gecko-collector

# Drop and recreate database
psql -h localhost -U postgres -c "DROP DATABASE IF EXISTS $DB_NAME;"
psql -h localhost -U postgres -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

# Restore from backup
if [[ $BACKUP_FILE == *.gz ]]; then
    gunzip -c "$BACKUP_FILE" | psql -h localhost -U $DB_USER -d $DB_NAME
else
    psql -h localhost -U $DB_USER -d $DB_NAME -f "$BACKUP_FILE"
fi

# Start application
sudo systemctl start gecko-collector

echo "Database restored from $BACKUP_FILE"
```

## Maintenance Procedures

### Regular Maintenance Tasks

#### Daily Tasks
```bash
#!/bin/bash
# daily-maintenance.sh

# Check system health
python -m gecko_terminal_collector.cli health-check

# Validate data integrity
python -m gecko_terminal_collector.cli validate-data --quick

# Clean up old logs
find /var/log/gecko-collector -name "*.log.*" -mtime +7 -delete

# Check disk space
df -h | awk '$5 > 80 {print "WARNING: " $0}'

# Update collection statistics
python -m gecko_terminal_collector.cli update-stats
```

#### Weekly Tasks
```bash
#!/bin/bash
# weekly-maintenance.sh

# Full data validation
python -m gecko_terminal_collector.cli validate-data --full

# Database optimization
python -m gecko_terminal_collector.cli optimize-db

# Performance analysis
python -m gecko_terminal_collector.cli performance-report --output /var/reports/

# Security updates
sudo apt update && sudo apt upgrade -y
```

#### Monthly Tasks
```bash
#!/bin/bash
# monthly-maintenance.sh

# Archive old data
python -m gecko_terminal_collector.cli archive-data --months 6

# Full database backup
pg_dump -h localhost -U gecko_user gecko_terminal_data | gzip > /var/backups/monthly_backup_$(date +%Y%m).sql.gz

# System resource analysis
python -m gecko_terminal_collector.cli resource-analysis --output /var/reports/

# Configuration review
python -m gecko_terminal_collector.cli config-audit
```

### Update Procedures

#### Application Updates
```bash
#!/bin/bash
# update-application.sh

VERSION="$1"

if [ -z "$VERSION" ]; then
    echo "Usage: $0 <version>"
    exit 1
fi

# Backup current installation
tar -czf "/var/backups/gecko-collector-$(date +%Y%m%d).tar.gz" /opt/gecko-terminal-collector

# Stop service
sudo systemctl stop gecko-collector

# Update application
cd /opt/gecko-terminal-collector
git fetch origin
git checkout "v$VERSION"
pip install -r requirements.txt
pip install -e .

# Run database migrations
python -m gecko_terminal_collector.cli migrate

# Validate configuration
python -m gecko_terminal_collector.cli validate-config

# Start service
sudo systemctl start gecko-collector

# Verify update
sleep 10
python -m gecko_terminal_collector.cli health-check

echo "Application updated to version $VERSION"
```

## Scaling Strategies

### Horizontal Scaling

#### Multi-Instance Deployment
```yaml
# docker-compose.scale.yml
version: '3.8'

services:
  gecko-collector-1:
    extends:
      file: docker-compose.production.yml
      service: gecko-collector
    environment:
      - INSTANCE_ID=1
      - COLLECTOR_TYPES=dex-monitoring,top-pools

  gecko-collector-2:
    extends:
      file: docker-compose.production.yml
      service: gecko-collector
    environment:
      - INSTANCE_ID=2
      - COLLECTOR_TYPES=ohlcv,trades

  gecko-collector-3:
    extends:
      file: docker-compose.production.yml
      service: gecko-collector
    environment:
      - INSTANCE_ID=3
      - COLLECTOR_TYPES=watchlist
```

#### Load Balancing
```nginx
# nginx-lb.conf
upstream gecko-collectors {
    least_conn;
    server gecko-collector-1:8080;
    server gecko-collector-2:8080;
    server gecko-collector-3:8080;
}

server {
    listen 80;
    
    location /metrics {
        proxy_pass http://gecko-collectors;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /health {
        proxy_pass http://gecko-collectors;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Vertical Scaling

#### Resource Optimization
```yaml
# config-high-performance.yaml
thresholds:
  max_concurrent_requests: 20
  rate_limit_delay: 0.5

database:
  pool_size: 100
  max_overflow: 200

system:
  worker_processes: 8
  memory_limit: "16GB"
  batch_size: 2000
```

### Database Scaling

#### Read Replicas
```yaml
# config-with-replicas.yaml
database:
  primary:
    url: "postgresql://gecko_user:${DB_PASSWORD}@db-primary:5432/gecko_terminal_data"
    pool_size: 50
  
  replicas:
    - url: "postgresql://gecko_user:${DB_PASSWORD}@db-replica-1:5432/gecko_terminal_data"
      pool_size: 20
    - url: "postgresql://gecko_user:${DB_PASSWORD}@db-replica-2:5432/gecko_terminal_data"
      pool_size: 20
```

#### Partitioning Strategy
```sql
-- Partition OHLCV data by date
CREATE TABLE ohlcv_data_2024_01 PARTITION OF ohlcv_data
FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE ohlcv_data_2024_02 PARTITION OF ohlcv_data
FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

-- Automated partition management
CREATE OR REPLACE FUNCTION create_monthly_partitions()
RETURNS void AS $$
DECLARE
    start_date date;
    end_date date;
    table_name text;
BEGIN
    start_date := date_trunc('month', CURRENT_DATE);
    end_date := start_date + interval '1 month';
    table_name := 'ohlcv_data_' || to_char(start_date, 'YYYY_MM');
    
    EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF ohlcv_data FOR VALUES FROM (%L) TO (%L)',
                   table_name, start_date, end_date);
END;
$$ LANGUAGE plpgsql;

-- Schedule partition creation
SELECT cron.schedule('create-partitions', '0 0 1 * *', 'SELECT create_monthly_partitions();');
```

## Disaster Recovery

### Disaster Recovery Plan

#### Recovery Time Objectives (RTO)
- **Critical Systems**: 15 minutes
- **Data Collection**: 30 minutes
- **Full System**: 2 hours

#### Recovery Point Objectives (RPO)
- **Database**: 1 hour (hourly backups)
- **Configuration**: 24 hours (daily backups)
- **Logs**: 24 hours (acceptable loss)

#### DR Procedures

1. **Immediate Response**
```bash
# Assess damage
python -m gecko_terminal_collector.cli system-status --detailed

# Stop affected services
sudo systemctl stop gecko-collector

# Check data integrity
python -m gecko_terminal_collector.cli validate-data --quick
```

2. **Recovery Steps**
```bash
# Restore from backup
./restore-database.sh /var/backups/gecko-collector/latest_backup.sql.gz

# Restore configuration
tar -xzf /var/backups/gecko-collector/config/latest_config.tar.gz -C /

# Restart services
sudo systemctl start gecko-collector

# Verify recovery
python -m gecko_terminal_collector.cli health-check --comprehensive
```

3. **Post-Recovery**
```bash
# Backfill missing data
python -m gecko_terminal_collector.cli backfill-missing --auto

# Update monitoring
python -m gecko_terminal_collector.cli update-monitoring-status

# Generate incident report
python -m gecko_terminal_collector.cli incident-report --output /var/reports/
```

### High Availability Setup

#### Active-Passive Configuration
```yaml
# ha-config.yaml
high_availability:
  mode: "active-passive"
  primary_node: "gecko-primary"
  secondary_node: "gecko-secondary"
  
  failover:
    health_check_interval: 30
    failure_threshold: 3
    automatic_failover: true
    
  data_replication:
    method: "streaming"
    sync_mode: "synchronous"
```

#### Cluster Management
```bash
#!/bin/bash
# cluster-manager.sh

PRIMARY_NODE="gecko-primary"
SECONDARY_NODE="gecko-secondary"

check_primary_health() {
    ssh $PRIMARY_NODE "python -m gecko_terminal_collector.cli health-check" > /dev/null 2>&1
    return $?
}

failover_to_secondary() {
    echo "Initiating failover to secondary node..."
    
    # Stop primary (if accessible)
    ssh $PRIMARY_NODE "sudo systemctl stop gecko-collector" 2>/dev/null
    
    # Promote secondary
    ssh $SECONDARY_NODE "sudo systemctl start gecko-collector"
    
    # Update load balancer
    update_load_balancer $SECONDARY_NODE
    
    echo "Failover completed"
}

# Main monitoring loop
while true; do
    if ! check_primary_health; then
        echo "Primary node health check failed"
        failover_to_secondary
        break
    fi
    sleep 30
done
```

## Compliance and Governance

### Data Governance

#### Data Retention Policy
```yaml
# retention-policy.yaml
data_retention:
  ohlcv_data:
    retention_period: "2 years"
    archive_after: "1 year"
    
  trade_data:
    retention_period: "1 year"
    archive_after: "6 months"
    
  logs:
    retention_period: "90 days"
    archive_after: "30 days"
    
  backups:
    retention_period: "1 year"
    offsite_storage: true
```

#### Data Privacy
```python
# data_privacy.py
class DataPrivacyManager:
    def anonymize_sensitive_data(self, data):
        """Remove or hash sensitive information."""
        # Remove IP addresses, user identifiers, etc.
        pass
    
    def audit_data_access(self, user, action, data_type):
        """Log data access for compliance."""
        audit_log = {
            'timestamp': datetime.now(),
            'user': user,
            'action': action,
            'data_type': data_type,
            'ip_address': self.get_client_ip()
        }
        self.log_audit_event(audit_log)
```

### Security Compliance

#### Security Audit Checklist
- [ ] All default passwords changed
- [ ] SSL/TLS certificates valid and up-to-date
- [ ] Firewall rules properly configured
- [ ] Database access restricted to necessary users
- [ ] Log files properly secured and rotated
- [ ] Backup encryption enabled
- [ ] Security updates applied regularly
- [ ] Access logs monitored for suspicious activity

#### Compliance Reporting
```bash
#!/bin/bash
# compliance-report.sh

REPORT_DATE=$(date +%Y-%m-%d)
REPORT_FILE="/var/reports/compliance-report-$REPORT_DATE.txt"

echo "Compliance Report - $REPORT_DATE" > $REPORT_FILE
echo "=================================" >> $REPORT_FILE

# Security checks
echo "Security Status:" >> $REPORT_FILE
python -m gecko_terminal_collector.cli security-audit >> $REPORT_FILE

# Data integrity
echo "Data Integrity:" >> $REPORT_FILE
python -m gecko_terminal_collector.cli validate-data --report >> $REPORT_FILE

# Backup status
echo "Backup Status:" >> $REPORT_FILE
python -m gecko_terminal_collector.cli backup-status >> $REPORT_FILE

# Access logs
echo "Access Summary:" >> $REPORT_FILE
python -m gecko_terminal_collector.cli access-summary --days 30 >> $REPORT_FILE

echo "Compliance report generated: $REPORT_FILE"
```

This operational guide provides a comprehensive framework for running the GeckoTerminal Data Collector system in production. Regular review and updates of these practices ensure optimal performance, security, and reliability.