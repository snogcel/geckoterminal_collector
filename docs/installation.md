# Installation Guide

This guide provides detailed instructions for installing and setting up the GeckoTerminal Data Collector.

## System Requirements

### Minimum Requirements
- Python 3.8 or higher
- 1GB RAM
- 5GB available disk space
- Internet connection for API access

### Recommended Requirements
- Python 3.9+
- 4GB RAM
- 50GB+ available disk space (for historical data)
- Stable internet connection with low latency

### Supported Operating Systems
- Linux (Ubuntu 18.04+, CentOS 7+)
- macOS 10.15+
- Windows 10+

## Installation Methods

### Method 1: Standard Installation

1. **Clone the Repository**
```bash
git clone <repository-url>
cd gecko-terminal-collector
```

2. **Create Virtual Environment** (Recommended)
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install Dependencies**
```bash
pip install -r requirements.txt
```

4. **Install the Package**
```bash
pip install -e .
```

### Method 2: Docker Installation

1. **Build Docker Image**
```bash
docker build -t gecko-terminal-collector .
```

2. **Run Container**
```bash
docker run -d \
  --name gecko-collector \
  -v $(pwd)/config.yaml:/app/config.yaml \
  -v $(pwd)/data:/app/data \
  gecko-terminal-collector
```

### Method 3: Development Installation

1. **Clone and Setup**
```bash
git clone <repository-url>
cd gecko-terminal-collector
python -m venv venv
source venv/bin/activate
```

2. **Install Development Dependencies**
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -e .
```

3. **Install Pre-commit Hooks**
```bash
pre-commit install
```

## Database Setup

### SQLite (Default)

SQLite requires no additional setup. The database file will be created automatically:

```bash
python -m gecko_terminal_collector.cli init-db
```

### PostgreSQL (Production)

1. **Install PostgreSQL**
```bash
# Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib

# macOS
brew install postgresql

# Windows
# Download from https://www.postgresql.org/download/windows/
```

2. **Create Database and User**
```sql
sudo -u postgres psql
CREATE DATABASE gecko_terminal_data;
CREATE USER gecko_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE gecko_terminal_data TO gecko_user;
\q
```

3. **Update Configuration**
```yaml
# config.yaml
database:
  url: "postgresql://gecko_user:your_password@localhost/gecko_terminal_data"
  pool_size: 20
  echo: false
```

4. **Initialize Database**
```bash
python -m gecko_terminal_collector.cli init-db
```

## Configuration Setup

1. **Copy Example Configuration**
```bash
cp config.yaml.example config.yaml
```

2. **Edit Configuration File**
```bash
nano config.yaml  # or your preferred editor
```

3. **Validate Configuration**
```bash
python -m gecko_terminal_collector.cli validate-config
```

## Environment Variables

You can override configuration values using environment variables:

```bash
export GECKO_DATABASE_URL="sqlite:///custom_path.db"
export GECKO_API_TIMEOUT=60
export GECKO_LOG_LEVEL=DEBUG
```

## Verification

### Test Installation
```bash
python -m gecko_terminal_collector.cli --help
```

### Test Database Connection
```bash
python -m gecko_terminal_collector.cli test-db
```

### Test API Connection
```bash
python -m gecko_terminal_collector.cli test-api
```

### Run Health Check
```bash
python -m gecko_terminal_collector.cli health-check
```

## Post-Installation Steps

1. **Create Watchlist File**
```bash
touch watchlist.csv
# Add your tokens to monitor (see Configuration Guide)
```

2. **Start Initial Collection**
```bash
python -m gecko_terminal_collector.cli collect --type dex-monitoring
```

3. **Verify Data Collection**
```bash
python -m gecko_terminal_collector.cli status
```

## Troubleshooting Installation

### Common Issues

**Python Version Error**
```bash
python --version  # Ensure 3.8+
```

**Permission Errors**
```bash
sudo chown -R $USER:$USER /path/to/gecko-terminal-collector
```

**Database Connection Issues**
- Check database service is running
- Verify connection string in config.yaml
- Test with: `python -m gecko_terminal_collector.cli test-db`

**API Connection Issues**
- Check internet connectivity
- Verify GeckoTerminal API status
- Test with: `python -m gecko_terminal_collector.cli test-api`

### Getting Help

If you encounter issues:
1. Check the [Troubleshooting Guide](troubleshooting.md)
2. Review log files in `logs/` directory
3. Run with debug logging: `GECKO_LOG_LEVEL=DEBUG`
4. Open an issue with error details and system information

## Next Steps

After successful installation:
1. Read the [Configuration Guide](configuration.md)
2. Follow the [User Guide](user_guide.md) to start collecting data
3. Review [Operational Best Practices](operational_best_practices.md) for production deployment