
(gecko_env_3_11) jon@dash-node01:~/sites/geckoterminal_collector$ python -m gecko_terminal_collector.cli add-watchlist --pool-id solana_F5vAiFCP82RQetoxK7ax4dNQCwqk2yez6aisAbFPenJ2 --symbol "Butterfly / SOL" --name "Butterfly / SOL" --network-address 4Ds7cxJ82gm34gV22zo2LjPdX3nFbQk9PXK7mjX4pump --active true
Adding watchlist entry...
Pool ID: solana_F5vAiFCP82RQetoxK7ax4dNQCwqk2yez6aisAbFPenJ2
Symbol: Butterfly / SOL
Name: Butterfly / SOL
Network Address: 4Ds7cxJ82gm34gV22zo2LjPdX3nFbQk9PXK7mjX4pump
Active: True
INFO: Database connection initialized
INFO: Creating database tables
INFO: Database tables created successfully
INFO: Applied SQLite concurrency optimizations
INFO: SQLAlchemy database manager initialized
Creating minimal pool entry for solana_F5vAiFCP82RQetoxK7ax4dNQCwqk2yez6aisAbFPenJ2...
✅ Created minimal pool entry
INFO: Added watchlist entry for pool: solana_F5vAiFCP82RQetoxK7ax4dNQCwqk2yez6aisAbFPenJ2
✅ Successfully added 'Butterfly / SOL' to watchlist
   Pool ID: solana_F5vAiFCP82RQetoxK7ax4dNQCwqk2yez6aisAbFPenJ2
   Total active watchlist entries: 1
INFO: Synchronous database engine disposed
INFO: SQLAlchemy database manager closed



(gecko_env_3_11) jon@dash-node01:~/sites/geckoterminal_collector$ python -m gecko_terminal_collector.cli list-watchlist
INFO: Database connection initialized
INFO: Creating database tables
INFO: Database tables created successfully
INFO: Applied SQLite concurrency optimizations
INFO: SQLAlchemy database manager initialized
ID    Pool ID                                            Symbol     Name                           Active   Added
-----------------------------------------------------------------------------------------------------------------------------
1     solana_F5vAiFCP82RQetoxK7ax4dNQCwqk2yez6aisAbFPenJ2 Butterfly / SOL Butterfly / SOL                True     2025-09-26 09:09:34

Total entries: 1
Active entries: 1
INFO: Synchronous database engine disposed
INFO: SQLAlchemy database manager closed

# TODO -- this kind of works, need to use scheduler to actually capture data
python -m gecko_terminal_collector.cli start

# Start Data Capture & Wait
python -m examples.cli_with_scheduler start

# In the meantime, collect historical OHLCV data

python collect_historical_with_rate_limits.py

## Wait.... Patience....

# SQLite is not powerful enough for this system, time to set up postgres

# Database Configuration
database:
  url: "postgresql://gecko_terminal_collector_user:12345678!@localhost:5432/gecko_collector"  # Database connection URL
  pool_size: 10                   # Connection pool size
  echo: false                     # Enable SQL query logging
  timeout: 30                     # Connection timeout (seconds)




















psql

\q

exit

# TODO -- document postgres setup process

# attempt to launch terminal_collector using
python -m gecko_terminal_collector.cli db-setup

python -m gecko_terminal_collector.cli add-watchlist --pool-id solana_F5vAiFCP82RQetoxK7ax4dNQCwqk2yez6aisAbFPenJ2 --symbol "Butterfly / SOL" --name "Butterfly / SOL" --network-address 4Ds7cxJ82gm34gV22zo2LjPdX3nFbQk9PXK7mjX4pump --active true


# second test coin
python -m gecko_terminal_collector.cli add-watchlist --pool-id solana_4w2cysotX6czaUGmmWg13hDpY4QEMG2CzeKYEQyK9Ama --symbol "TROLL / SOL" --name "TROLL / SOL" --network-address 5UUH9RTDiSpq6HKS6bp4NdU9PNJpXRXuiw6ShBTBhgH2 --active true


4w2cysotX6czaUGmmWg13hDpY4QEMG2CzeKYEQyK9Ama

5UUH9RTDiSpq6HKS6bp4NdU9PNJpXRXuiw6ShBTBhgH2

So11111111111111111111111111111111111111112











# Once Dependencies are installed, initialize SQLite Database

(gecko_env_3_11) jon@dash-node01:~/sites/geckoterminal_collector$ python -m gecko_terminal_collector.cli --help


(gecko_env_3_11) jon@dash-node01:~/sites/geckoterminal_collector$ python -m gecko_terminal_collector.cli init
Configuration file config.yaml already exists. Use --force to overwrite.

(gecko_env_3_11) jon@dash-node01:~/sites/geckoterminal_collector$ python -m gecko_terminal_collector.cli db-setup
Setting up database schema...
INFO: Database connection initialized
INFO: Creating database tables
INFO: Database tables created successfully
INFO: Applied SQLite concurrency optimizations
INFO: SQLAlchemy database manager initialized
INFO: Synchronous database engine disposed
INFO: SQLAlchemy database manager closed
Error setting up database: 'latin-1' codec can't encode character '\u2713' in position 0: ordinal not in range(256)


# Database Schema created successfully, latin-1 codec can't encode character
# fixable in ubuntu?

sudo update-locale LANG=en_US.UTF-8 LANGUAGE=en.UTF-8

sudo shutdown -r now


(gecko_env) jon@dash-node01:~/sites/geckoterminal_collector$ python -m gecko_terminal_collector.cli db-setup
Traceback (most recent call last):
  File "/home/jon/anaconda3/envs/gecko_env/lib/python3.9/runpy.py", line 188, in _run_module_as_main
    mod_name, mod_spec, code = _get_module_details(mod_name, _Error)
  File "/home/jon/anaconda3/envs/gecko_env/lib/python3.9/runpy.py", line 111, in _get_module_details
    __import__(pkg_name)
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/__init__.py", line 12, in <module>
    from .qlib import QLibExporter
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/qlib/__init__.py", line 5, in <module>
    from .exporter import QLibExporter
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/qlib/exporter.py", line 9, in <module>
    import pandas as pd
ModuleNotFoundError: No module named 'pandas'


> pip install pandas

(gecko_env) jon@dash-node01:~/sites/geckoterminal_collector$ python -m gecko_terminal_collector.cli db-setup
Traceback (most recent call last):
  File "/home/jon/anaconda3/envs/gecko_env/lib/python3.9/runpy.py", line 188, in _run_module_as_main
    mod_name, mod_spec, code = _get_module_details(mod_name, _Error)
  File "/home/jon/anaconda3/envs/gecko_env/lib/python3.9/runpy.py", line 111, in _get_module_details
    __import__(pkg_name)
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/__init__.py", line 12, in <module>
    from .qlib import QLibExporter
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/qlib/__init__.py", line 5, in <module>
    from .exporter import QLibExporter
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/qlib/exporter.py", line 16, in <module>
    from gecko_terminal_collector.database.manager import DatabaseManager
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/database/__init__.py", line 5, in <module>
    from .connection import DatabaseConnection
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/database/connection.py", line 9, in <module>
    from sqlalchemy import create_engine, event
ModuleNotFoundError: No module named 'sqlalchemy'

> pip install sqlalchemy

(gecko_env) jon@dash-node01:~/sites/geckoterminal_collector$ python -m gecko_terminal_collector.cli db-setup
Traceback (most recent call last):
  File "/home/jon/anaconda3/envs/gecko_env/lib/python3.9/runpy.py", line 188, in _run_module_as_main
    mod_name, mod_spec, code = _get_module_details(mod_name, _Error)
  File "/home/jon/anaconda3/envs/gecko_env/lib/python3.9/runpy.py", line 111, in _get_module_details
    __import__(pkg_name)
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/__init__.py", line 12, in <module>
    from .qlib import QLibExporter
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/qlib/__init__.py", line 5, in <module>
    from .exporter import QLibExporter
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/qlib/exporter.py", line 16, in <module>
    from gecko_terminal_collector.database.manager import DatabaseManager
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/database/__init__.py", line 5, in <module>
    from .connection import DatabaseConnection
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/database/connection.py", line 15, in <module>
    from gecko_terminal_collector.config.models import DatabaseConfig
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/config/__init__.py", line 16, in <module>
    from .manager import ConfigManager
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/config/manager.py", line 6, in <module>
    import yaml
ModuleNotFoundError: No module named 'yaml'

> pip install pyyaml

(gecko_env) jon@dash-node01:~/sites/geckoterminal_collector$ python -m gecko_terminal_collector.cli db-setup
Traceback (most recent call last):
  File "/home/jon/anaconda3/envs/gecko_env/lib/python3.9/runpy.py", line 188, in _run_module_as_main
    mod_name, mod_spec, code = _get_module_details(mod_name, _Error)
  File "/home/jon/anaconda3/envs/gecko_env/lib/python3.9/runpy.py", line 111, in _get_module_details
    __import__(pkg_name)
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/__init__.py", line 12, in <module>
    from .qlib import QLibExporter
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/qlib/__init__.py", line 5, in <module>
    from .exporter import QLibExporter
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/qlib/exporter.py", line 16, in <module>
    from gecko_terminal_collector.database.manager import DatabaseManager
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/database/__init__.py", line 5, in <module>
    from .connection import DatabaseConnection
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/database/connection.py", line 15, in <module>
    from gecko_terminal_collector.config.models import DatabaseConfig
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/config/__init__.py", line 16, in <module>
    from .manager import ConfigManager
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/config/manager.py", line 13, in <module>
    from watchdog.observers import Observer
ModuleNotFoundError: No module named 'watchdog'

> pip install watchdog

(gecko_env) jon@dash-node01:~/sites/geckoterminal_collector$ python -m gecko_terminal_collector.cli db-setup
Traceback (most recent call last):
  File "/home/jon/anaconda3/envs/gecko_env/lib/python3.9/runpy.py", line 188, in _run_module_as_main
    mod_name, mod_spec, code = _get_module_details(mod_name, _Error)
  File "/home/jon/anaconda3/envs/gecko_env/lib/python3.9/runpy.py", line 111, in _get_module_details
    __import__(pkg_name)
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/__init__.py", line 12, in <module>
    from .qlib import QLibExporter
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/qlib/__init__.py", line 5, in <module>
    from .exporter import QLibExporter
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/qlib/exporter.py", line 16, in <module>
    from gecko_terminal_collector.database.manager import DatabaseManager
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/database/__init__.py", line 5, in <module>
    from .connection import DatabaseConnection
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/database/connection.py", line 15, in <module>
    from gecko_terminal_collector.config.models import DatabaseConfig
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/config/__init__.py", line 16, in <module>
    from .manager import ConfigManager
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/config/manager.py", line 16, in <module>
    from gecko_terminal_collector.config.validation import (
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/config/validation.py", line 8, in <module>
    from pydantic import BaseModel, Field, field_validator, model_validator
ModuleNotFoundError: No module named 'pydantic'

> pip install pydantic

(gecko_env) jon@dash-node01:~/sites/geckoterminal_collector$ python -m gecko_terminal_collector.cli db-setup
Traceback (most recent call last):
  File "/home/jon/anaconda3/envs/gecko_env/lib/python3.9/runpy.py", line 188, in _run_module_as_main
    mod_name, mod_spec, code = _get_module_details(mod_name, _Error)
  File "/home/jon/anaconda3/envs/gecko_env/lib/python3.9/runpy.py", line 111, in _get_module_details
    __import__(pkg_name)
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/__init__.py", line 12, in <module>
    from .qlib import QLibExporter
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/qlib/__init__.py", line 5, in <module>
    from .exporter import QLibExporter
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/qlib/exporter.py", line 16, in <module>
    from gecko_terminal_collector.database.manager import DatabaseManager
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/database/__init__.py", line 7, in <module>
    from .migrations import MigrationManager, create_migration_manager
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/database/migrations.py", line 10, in <module>
    from alembic import command
ModuleNotFoundError: No module named 'alembic'

> pip install alembic

(gecko_env) jon@dash-node01:~/sites/geckoterminal_collector$ python -m gecko_terminal_collector.cli db-setup
Traceback (most recent call last):
  File "/home/jon/anaconda3/envs/gecko_env/lib/python3.9/runpy.py", line 188, in _run_module_as_main
    mod_name, mod_spec, code = _get_module_details(mod_name, _Error)
  File "/home/jon/anaconda3/envs/gecko_env/lib/python3.9/runpy.py", line 111, in _get_module_details
    __import__(pkg_name)
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/__init__.py", line 13, in <module>
    from .utils.enhanced_rate_limiter import EnhancedRateLimiter, GlobalRateLimitCoordinator
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/utils/__init__.py", line 8, in <module>
    from .bootstrap import SystemBootstrap, BootstrapResult, BootstrapProgress, BootstrapError
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/utils/bootstrap.py", line 19, in <module>
    from gecko_terminal_collector.collectors.discovery_engine import DiscoveryEngine, DiscoveryResult
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/collectors/__init__.py", line 5, in <module>
    from .base import BaseDataCollector, CollectorRegistry
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/collectors/base.py", line 13, in <module>
    from gecko_terminal_collector.clients import BaseGeckoClient, create_gecko_client
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/clients/__init__.py", line 5, in <module>
    from .gecko_client import GeckoTerminalClient, MockGeckoTerminalClient, BaseGeckoClient
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/clients/gecko_client.py", line 15, in <module>
    import aiohttp
ModuleNotFoundError: No module named 'aiohttp'

> pip install aiohttp

(gecko_env) jon@dash-node01:~/sites/geckoterminal_collector$ python -m gecko_terminal_collector.cli db-setup
Traceback (most recent call last):
  File "/home/jon/anaconda3/envs/gecko_env/lib/python3.9/runpy.py", line 188, in _run_module_as_main
    mod_name, mod_spec, code = _get_module_details(mod_name, _Error)
  File "/home/jon/anaconda3/envs/gecko_env/lib/python3.9/runpy.py", line 111, in _get_module_details
    __import__(pkg_name)
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/__init__.py", line 13, in <module>
    from .utils.enhanced_rate_limiter import EnhancedRateLimiter, GlobalRateLimitCoordinator
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/utils/__init__.py", line 8, in <module>
    from .bootstrap import SystemBootstrap, BootstrapResult, BootstrapProgress, BootstrapError
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/utils/bootstrap.py", line 19, in <module>
    from gecko_terminal_collector.collectors.discovery_engine import DiscoveryEngine, DiscoveryResult
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/collectors/__init__.py", line 5, in <module>
    from .base import BaseDataCollector, CollectorRegistry
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/collectors/base.py", line 13, in <module>
    from gecko_terminal_collector.clients import BaseGeckoClient, create_gecko_client
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/clients/__init__.py", line 5, in <module>
    from .gecko_client import GeckoTerminalClient, MockGeckoTerminalClient, BaseGeckoClient
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/clients/gecko_client.py", line 16, in <module>
    from geckoterminal_py import GeckoTerminalAsyncClient
ModuleNotFoundError: No module named 'geckoterminal_py'











# From there, install SQLite or Postgres



## For now, testing with SQLite

# SQLite (Default)
# SQLite requires no additional setup. The database file will be created automatically:

(gecko_env_3_11) jon@dash-node01:~/sites/geckoterminal_collector$ python -m gecko_terminal_collector.cli init-db
Traceback (most recent call last):
  File "<frozen runpy>", line 189, in _run_module_as_main
  File "<frozen runpy>", line 112, in _get_module_details
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/__init__.py", line 13, in <module>
    from .utils.enhanced_rate_limiter import EnhancedRateLimiter, GlobalRateLimitCoordinator
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/utils/__init__.py", line 8, in <module>
    from .bootstrap import SystemBootstrap, BootstrapResult, BootstrapProgress, BootstrapError
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/utils/bootstrap.py", line 19, in <module>
    from gecko_terminal_collector.collectors.discovery_engine import DiscoveryEngine, DiscoveryResult
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/collectors/__init__.py", line 5, in <module>
    from .base import BaseDataCollector, CollectorRegistry
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/collectors/base.py", line 17, in <module>
    from gecko_terminal_collector.utils.resilience import HealthChecker, HealthStatus
  File "/home/jon/sites/geckoterminal_collector/gecko_terminal_collector/utils/resilience.py", line 15, in <module>
    import psutil
ModuleNotFoundError: No module named 'psutil'

> pip install psutil

(gecko_env_3_11) jon@dash-node01:~/sites/geckoterminal_collector$ pip install psutil
Collecting psutil
  Downloading psutil-7.1.0-cp36-abi3-manylinux_2_12_x86_64.manylinux2010_x86_64.manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (23 kB)
Downloading psutil-7.1.0-cp36-abi3-manylinux_2_12_x86_64.manylinux2010_x86_64.manylinux_2_17_x86_64.manylinux2014_x86_64.whl (291 kB)
Installing collected packages: psutil
Successfully installed psutil-7.1.0


(gecko_env_3_11) jon@dash-node01:~/sites/geckoterminal_collector$ python -m gecko_terminal_collector.cli init-db
usage: cli.py [-h] [--version] [--config CONFIG] [--verbose] [--quiet]
              {init,validate,db-setup,start,stop,status,run-collector,backfill,export,cleanup,health-check,metrics,logs,backup,restore,build-ohlcv,validate-workflow,migrate-pool-ids,add-watchlist,list-watchlist,update-watchlist,remove-watchlist,collect-new-pools,analyze-pool-discovery,analyze-pool-signals,monitor-pool-signals,db-health,db-monitor}
              ...
cli.py: error: argument command: invalid choice: 'init-db' (choose from 'init', 'validate', 'db-setup', 'start', 'stop', 'status', 'run-collector', 'backfill', 'export', 'cleanup', 'health-check', 'metrics', 'logs', 'backup', 'restore', 'build-ohlcv', 'validate-workflow', 'migrate-pool-ids', 'add-watchlist', 'list-watchlist', 'update-watchlist', 'remove-watchlist', 'collect-new-pools', 'analyze-pool-discovery', 'analyze-pool-signals', 'monitor-pool-signals', 'db-health', 'db-monitor')

 python -m gecko_terminal_collector.cli init

Configuration file config.yaml already exists. Use --force to overwrite.


# to start collector, run:

python examples/cli_with_scheduler.py start

# results in output:

(gecko_env_3_11) jon@dash-node01:~/sites/geckoterminal_collector$ python examples/cli_with_scheduler.py start
Traceback (most recent call last):
  File "/home/jon/sites/geckoterminal_collector/examples/cli_with_scheduler.py", line 18, in <module>
    from gecko_terminal_collector.config.models import CollectionConfig
ModuleNotFoundError: No module named 'gecko_terminal_collector'

 python -m examples.cli_with_scheduler start


## Likely need to update config.yaml

# comment out previous localhost postgres configuration (on other laptop)

# Database Configuration
#database:
#  url: "postgresql://gecko_collector:12345678!@localhost:5432/gecko_terminal_collector"  # Database connection URL
#  pool_size: 10                   # Connection pool size
#  echo: false                     # Enable SQL query logging
#  timeout: 30                     # Connection timeout (seconds)

# Comment out NautilusTrader POC Configuration (because it hasn't been developed yet)


(gecko_env_3_11) jon@dash-node01:~/sites/geckoterminal_collector$ python -m examples.cli_with_scheduler start


# TODO -- remember to use CLI to start / stop




TODO - initialize SQLite Database






















sudo apt-get update

sudo apt update

upgrade?



// sudo apt-get install rustc
// sudo apt-get install cargo








(gecko_env_3_11) jon@dash-node01:~/sites/geckoterminal_collector$ rustc -V
rustc 1.53.0 (53cb7b09b 2021-06-17)








# The Truth Hurts:
- Windows
- Linux
# Two Different Operating Sytems.




# Verify Build Dependencies #

curl https://sh.rustup.rs -sSf | sh



# Step 1: create python environment OR use local python installation

conda create -n gecko_env_3_11 python=3.11 

## might encounter error: *dependency_1* *error_1* *error_2* *error_3*

conda activate gecko_env_3_11








# ERROR_3 # *error_3*

(gecko_env) jon@dash-node01:~/sites/geckoterminal_collector$ pip install -r requirements.txt
ERROR: Ignored the following versions that require a different python version: 0.1.0 Requires-Python <4.0,>=3.10; 0.1.1 Requires-Python <4.0,>=3.10; 0.1.3 Requires-Python <4.0,>=3.10; 0.2.0 Requires-Python <4.0,>=3.10; 0.2.1 Requires-Python <4.0,>=3.10; 0.2.2 Requires-Python <4.0,>=3.10; 0.2.3 Requires-Python <4.0,>=3.10; 0.2.4 Requires-Python <4.0,>=3.10; 0.2.5 Requires-Python >=3.10
ERROR: Could not find a version that satisfies the requirement geckoterminal-py>=0.2.5 (from versions: 0.1.2)
ERROR: No matching distribution found for geckoterminal-py>=0.2.5

# END_ERROR_3 ###




# ERROR_2 # *error_2*

conda: error: argument COMMAND: invalid choice: 'activate' (choose from 'clean', 'compare', 'config', 'create', 'info', 'init', 'install', 'list', 'notices', 'package', 'remove', 'uninstall', 'rename', 'run', 'search', 'update', 'upgrade', 'build', 'content-trust', 'convert', 'debug', 'develop', 'doctor', 'index', 'inspect', 'metapackage', 'render', 'skeleton', 'verify', 'env', 'pack', 'repo', 'server', 'token')

> this indicates that the installation of anaconda3 did not complete successfully. Use the following command to initialize it:

conda init bash

# END_ERROR_2 #









# BUILD DEPENDENCIES #

# Check Python Version on VPS -- in this case Python 3.11, which is a little different than 3.9 but worth trying as it's more recent than python 3.9

python --version

> Python 3.11.5

# in this case, we need to remove reference to Anaconda3 and use local python build tools - because Anaconda3 is already installed, and gecko_env already created, simply close terminal and reopen "did you try turning it off, then back on?"

  The above exception was the direct cause of the following exception:

  Traceback (most recent call last):
    File "/tmp/pip-install-o28c8xbp/nautilus-trader_de708b42b2b045e88a73cbbc467f87d2/build.py", line 552, in <module>
      build()
    File "/tmp/pip-install-o28c8xbp/nautilus-trader_de708b42b2b045e88a73cbbc467f87d2/build.py", line 484, in build
      _build_rust_libs()
    File "/tmp/pip-install-o28c8xbp/nautilus-trader_de708b42b2b045e88a73cbbc467f87d2/build.py", line 177, in _build_rust_libs
      raise RuntimeError(
  RuntimeError: Error running cargo: Command '['cargo', 'build', '--lib', '-p', 'nautilus-backtest', '-p', 'nautilus-common', '-p', 'nautilus-core', '-p',                                         'nautilus-infrastructure', '-p', 'nautilus-model', '-p', 'nautilus-persistence', '-p', 'nautilus-pyo3', '--release', '--no-default-features', '--features',                                         'ffi,python,extension-module,postgres,high-precision']' returned non-zero exit status 101.
  Traceback (most recent call last):
    File "/home/jon/anaconda3/lib/python3.11/site-packages/pip/_vendor/pyproject_hooks/_in_process/_in_process.py", line 353, in <module>
      main()
    File "/home/jon/anaconda3/lib/python3.11/site-packages/pip/_vendor/pyproject_hooks/_in_process/_in_process.py", line 335, in main
      json_out['return_val'] = hook(**hook_input['kwargs'])
                               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/jon/anaconda3/lib/python3.11/site-packages/pip/_vendor/pyproject_hooks/_in_process/_in_process.py", line 251, in build_wheel
      return _build_backend().build_wheel(wheel_directory, config_settings,
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/tmp/pip-build-env-a1oziynq/overlay/lib/python3.11/site-packages/poetry/core/masonry/api.py", line 58, in build_wheel
      return WheelBuilder.make_in(
             ^^^^^^^^^^^^^^^^^^^^^
    File "/tmp/pip-build-env-a1oziynq/overlay/lib/python3.11/site-packages/poetry/core/masonry/builders/wheel.py", line 95, in make_in
      wb.build(target_dir=directory)
    File "/tmp/pip-build-env-a1oziynq/overlay/lib/python3.11/site-packages/poetry/core/masonry/builders/wheel.py", line 134, in build
      self._build(zip_file)
    File "/tmp/pip-build-env-a1oziynq/overlay/lib/python3.11/site-packages/poetry/core/masonry/builders/wheel.py", line 183, in _build
      self._run_build_script(self._package.build_script)
    File "/tmp/pip-build-env-a1oziynq/overlay/lib/python3.11/site-packages/poetry/core/masonry/builders/wheel.py", line 304, in _run_build_script
      subprocess.check_call([self.executable.as_posix(), build_script])
    File "/home/jon/anaconda3/lib/python3.11/subprocess.py", line 413, in check_call
      raise CalledProcessError(retcode, cmd)
  subprocess.CalledProcessError: Command '['/home/jon/anaconda3/bin/python', 'build.py']' returned non-zero exit status 1.
  [end of output]

  note: This error originates from a subprocess, and is likely not a problem with pip.
  ERROR: Failed building wheel for nautilus_trader
  Building wheel for construct (setup.py) ... done

# if build errors still persist, one option is to refer to the nautilus documentation:

pip install -U nautilus_trader --pre --index-url=https://packages.nautechsystems.io/simple















## DEPENDENCIES ##

# DEPENDENCY_2: Miniconda is similar to Anaconda, but with different parsing inputs (guessing)

# DEPENDENCY_1: Anaconda makes Python Development much easier, but not required # *dependency_1*

# install conda on VPS

sudo apt-get update

# get latest installer
wget https://repo.anaconda.com/archive/Anaconda3-2025.06-0-Linux-x86_64.sh

# follow installation instructions readily available online.
# possible errors include

1. ERROR_1 *error_1* 
- conda: command not found



###### #############

# Possible Errors:


# ERROR 1 ##### *error_1*
conda: command not found

# Ubuntu 20.04

open ~/.bashrc

# add the following line
export PATH="/path/to/your/conda/bin:$PATH"

# in the case of my development server:
export PATH="/home/jon/anaconda3/bin:$PATH"

# reload terminal settings (or close and reopen)
source ~/.bashrc

#### ##############









