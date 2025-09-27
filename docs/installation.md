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

### Development Installation

No cryptocurrency wallet functionality is included in this release, and this application does not currently perform any trading functions. This is a data collection platform, more information on how trading functionality could be included is in the following specification: https://github.com/snogcel/geckoterminal_collector/blob/main/.kiro/specs/nautilus-trader-poc/tasks.md. 

This application is preconfigured to use SQLite, this should be for validation of the data collection platform. 

SQLite is used as a default installation method and for validation of development environment. Postgres should be used after development environment has been established.

```
Distributor ID: Ubuntu
Description:    Ubuntu 20.04.6 LTS
Release:        20.04
Codename:       focal
```

1. **Build Requirements**
```bash
sudo apt update && sudo apt upgrade
sudo apt-get install build-essential rustc cargo
```

2. **Update the Rust Toolchain**

Please see: https://phoenixnap.com/kb/install-rust-ubuntu

```bash
rustup update
```

3. **Configure Python 3.11 Environment**

Please see: https://www.geeksforgeeks.org/linux-unix/how-to-install-anaconda-on-ubuntu-20-04/

```bash
conda create -n gecko_env_3_11 python=3.11 
```

4. **Activate Conda Environment**

```bash
conda activate gecko_env_3_11
```

5. **Install Python Packages**
```bash
pip install -r requirements.txt
```

6. **Validate Development Environment**
```bash
python -m gecko_terminal_collector.cli db-setup

python -m gecko_terminal_collector.cli validate

python -m gecko_terminal_collector.cli add-watchlist --pool-id solana_F5vAiFCP82RQetoxK7ax4dNQCwqk2yez6aisAbFPenJ2 --symbol "Butterfly / SOL" --name "Butterfly / SOL" --network-address 4Ds7cxJ82gm34gV22zo2LjPdX3nFbQk9PXK7mjX4pump --active true

python -m gecko_terminal_collector.cli list-watchlist
```

7. **Configure Postgres Server**
Please see: https://www.digitalocean.com/community/tutorials/how-to-install-postgresql-on-ubuntu-20-04-quickstart

```bash
sudo apt update

sudo apt install postgresql postgresql-contrib

sudo systemctl start postgresql.service

sudo -i -u postgres

createuser --interactive
```

8. **Enter name of role to add:**

```bash
gecko_collector
```

9. **Shall the new role be a superuser? (y/n)**
```bash
y
```

10. **Create New Database**
```bash
createdb gecko_collector gecko_terminal_collector
```

In this example, we are using two users:

superuser: gecko_terminal_collector

user: gecko_terminal_collector_user

11. **Next, configure the user account for data collection**
```bash
CREATE USER gecko_terminal_collector_user WITH ENCRYPTED PASSWORD 'WS#$KHZKSDghs';
GRANT ALL PRIVILEGES ON DATABASE gecko_collector TO gecko_terminal_collector_user;
```

12. **Exit psql**
```bash
exit
```

13. **Exit postgres user and return to normal linux user**

See: https://askubuntu.com/questions/70534/what-are-the-differences-between-su-sudo-s-sudo-i-sudo-su

```bash
exit
```

14. **At this point, you're ready to begin capturing data**
```bash
python -m examples.cli_with_scheduler start
```

15. **To collect Historical OHLCV Data, use the following command**
```bash
python collect_historical_with_rate_limits.py
```

16. **To export Historical OHLCV Data, use the following command**

```bash
python -m gecko_terminal_collector.cli export --format qlib --output TROLL
INFO: Database connection initialized
INFO: Creating database tables
INFO: Database tables created successfully
INFO: Using PostgreSQL database - no additional optimizations needed
INFO: SQLAlchemy database manager initialized
Exporting data in qlib format to TROLL
INFO: QLibExporter initialized with basic symbol mapping
INFO: Retrieved 2 symbols for QLib export
INFO: Exported 1045 records for 2 symbols
INFO: Successfully exported 2 files with 1045 total records
✓ Export completed successfully
  Files created: 2
  Total records: 1045
INFO: Synchronous database engine disposed
INFO: SQLAlchemy database manager closed
```

The result will be a package of data stored in a folder titled "TROLL", containing a JSON summary file of the export. 

*Example*
```bash
{
  "export_date": "2025-09-27T11:09:25.856106",
  "timeframe": "1h",
  "symbols_exported": 2,
  "date_range": {
    "start": "2025-08-16T05:00:00",
    "end": "2025-09-27T00:00:00"
  },
  "success": true,
  "files_created": 2,
  "total_records": 1045
}
```

This folder will contain export data in two formats: CSV, XLSX.

17. **Create Wrapper Script**

Create a bash script (titled geckoterminal_collector.sh in this example)

```bash
#!/bin/bash

# Source the conda initialization script
source /home/jon/anaconda3/etc/profile.d/conda.sh

# Activate your specific conda environment
conda activate gecko_env_3_11

# Execute your Python script or application
# Use -u for unbuffered output, which is often helpful for logging in systemd
cd ~/sites/geckoterminal_collector
python -m examples.cli_with_scheduler start
```

18. **Set Permissions on Wrapper Bash Script**

Set script permissions to allow execution

```bash
chmod +x /home/jon/geckoterminal_collector.sh
```

19. **Configure System Service**

see: https://www.digitalocean.com/community/tutorials/how-to-use-systemctl-to-manage-systemd-services-and-units

```bash
[Unit]
Description=geckoterminal_collector_service
After=network.target

[Service]
Type=simple
User=jon
ExecStart=/home/jon/geckoterminal_collector.sh
Restart=on-failure
WorkingDirectory=/home/jon/sites/geckoterminal_collector

[Install]
WantedBy=multi-user.target
```

18. **Test Service Configuration**

```bash
sudo systemctl start geckoterminal_collector.service

sudo systemctl stop geckoterminal_collector.service
```

19. **Start Service on System Restart**

```bash
sudo systemctl enable geckoterminal_collector.service
```

20. **Check on Collector Status**

21. **PSQL**

22. **Query Tables**



## Known Bugs (please feel free to submit Pull Requests)

(gecko_env_3_11) jon@dash-node01:~/sites/geckoterminal_collector$ python -m gecko_terminal_collector.cli export --format csv --output TROLL
INFO: Database connection initialized
INFO: Creating database tables
INFO: Database tables created successfully
INFO: Using PostgreSQL database - no additional optimizations needed
INFO: SQLAlchemy database manager initialized
Exporting data in csv format to TROLL
Export format 'csv' not yet implemented


(gecko_env_3_11) jon@dash-node01:~/sites/geckoterminal_collector$ python -m gecko_terminal_collector.cli export --format json --output TROLL
INFO: Database connection initialized
INFO: Creating database tables
INFO: Database tables created successfully
INFO: Using PostgreSQL database - no additional optimizations needed
INFO: SQLAlchemy database manager initialized
Exporting data in json format to TROLL
Export format 'json' not yet implemented

- 2025-09-26 10:21:10,832 - gecko_terminal_collector.collectors.base.NewPoolsCollector - ERROR - Error ensuring pool exists for solana_DzNHbC9N4eZd9Yab6QfZfAxmXBRNoSrFboLvzyufxU2c: 'latin-1' codec can't encode characters in position 0-2: ordinal not in range(256)
- 2025-09-26 10:21:10,835 - gecko_terminal_collector.database.sqlalchemy_manager - ERROR - Error storing new pools history record: 'latin-1' codec can't encode characters in position 0-2: ordinal not in range(256)
- 2025-09-26 10:21:10,835 - gecko_terminal_collector.collectors.base.NewPoolsCollector - ERROR - Error storing history record for solana_DzNHbC9N4eZd9Yab6QfZfAxmXBRNoSrFboLvzyufxU2c: 'latin-1' codec can't encode characters in position 0-2: ordinal not in range(256)
- 2025-09-26 10:21:10,835 - gecko_terminal_collector.collectors.base.NewPoolsCollector - ERROR - Error processing pool solana_DzNHbC9N4eZd9Yab6QfZfAxmXBRNoSrFboLvzyufxU2c: 'latin-1' codec can't encode characters in position 0-2: ordinal not in range(256)
- 2025-09-26 10:21:10,842 - gecko_terminal_collector.collectors.base.NewPoolsCollector - ERROR - Error ensuring pool exists for solana_3ibg5GiKe3BTLbJZW4JfPtZvjJ4GCtCsNqZUAb3c2nPa: 'latin-1' codec can't encode characters in position 0-2: ordinal not in range(256)
- 2025-09-26 10:21:10,845 - gecko_terminal_collector.database.sqlalchemy_manager - ERROR - Error storing new pools history record: 'latin-1' codec can't encode characters in position 0-2: ordinal not in range(256)

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