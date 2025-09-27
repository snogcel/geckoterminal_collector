## DEV Environment # 
# Windows

#### ###############

# TODO
1. Document Installation Process a second time to make it easy for people to test.
2. SQLite is great for environment validation, but will fail when capturing data.
3. Recommend using postgres for production environment.

## VPS Production Server SETUP ##

Distributor ID: Ubuntu
Description:    Ubuntu 20.04.6 LTS
Release:        20.04
Codename:       focal

# Recommend using Anaconda3

# Update system packages
sudo apt-get install build-essential rustc cargo
sudo apt update && sudo apt upgrade

# Update the Rust toolchain
rustup update

# Activate Python 3.11 Environment
conda create -n gecko_env_3_11 python=3.11 

## might encounter error: *dependency_1* *error_1* *error_2* *error_3*
conda activate gecko_env_3_11

# install using pip
pip install -r requirements.txt

# TODO - update documentation, requires Python 3.11
# TODO - requires rust build tools

# https://phoenixnap.com/kb/install-rust-ubuntu 
# install anaconda, python version 3.11
# install cargo, which is a rust package manager
# install using "pip install -r requirements.txt", then initialize database


# Initialize Database

python -m gecko_terminal_collector.cli db-setup

python -m gecko_terminal_collector.cli validate

python -m gecko_terminal_collector.cli list-watchlist

# Launched a day ago, seems reasonably legit
# https://dexscreener.com/solana/f5vaifcp82rqetoxk7ax4dnqcwqk2yez6aisabfpenj2

python -m gecko_terminal_collector.cli add-watchlist --pool-id solana_F5vAiFCP82RQetoxK7ax4dNQCwqk2yez6aisAbFPenJ2 --symbol "Butterfly / SOL" --name "Butterfly / SOL" --network-address 4Ds7cxJ82gm34gV22zo2LjPdX3nFbQk9PXK7mjX4pump --active TRUE

usage: cli.py add-watchlist [-h] --pool-id POOL_ID --symbol SYMBOL [--name NAME] [--network-address NETWORK_ADDRESS] [--active {true,false}]
                            [--config CONFIG]



# Setup Local Postgres Server

https://www.digitalocean.com/community/tutorials/how-to-install-postgresql-on-ubuntu-20-04-quickstart


sudo apt update

sudo apt install postgresql postgresql-contrib

sudo systemctl start postgresql.service

sudo -i -u postgres

createuser --interactive

# Enter name of role to add:

gecko_collector

# Shall the new role be a superuser? (y/n)

y

createdb gecko_collector gecko_terminal_collector

# superuser: gecko_terminal_collector
# user: gecko_terminal_collector_user

# configure user account for data collection

CREATE USER gecko_terminal_collector_user WITH ENCRYPTED PASSWORD 'WS#$KHZKSDghs';
GRANT ALL PRIVILEGES ON DATABASE gecko_collector TO gecko_terminal_collector_user;

# exit psql
exit

# exit postgres user scope
exit

## Example:

postgres=# GRANT ALL PRIVILEGES ON DATABASE gecko_collector TO gecko_terminal_collector_user;
GRANT
postgres=# exit
postgres@SERVER:~$ exit
(gecko_env_3_11) user@SERVER:~/sites/geckoterminal_collector$



# Start Data Capture & Wait
python -m examples.cli_with_scheduler start

# In the meantime, collect historical OHLCV data

python collect_historical_with_rate_limits.py




# Access PSQL to review data entry

sudo -i -u postgres

# open psql

psql

# connect to newly created database

\c gecko_collector

# describe tables

\dt

You are now connected to database "gecko_collector" as user "postgres".
gecko_collector=# \dt
                          List of relations
 Schema |        Name         | Type  |             Owner
--------+---------------------+-------+-------------------------------
 public | collection_metadata | table | gecko_terminal_collector_user
 public | dexes               | table | gecko_terminal_collector_user
 public | discovery_metadata  | table | gecko_terminal_collector_user
 public | new_pools_history   | table | gecko_terminal_collector_user
 public | ohlcv_data          | table | gecko_terminal_collector_user
 public | pools               | table | gecko_terminal_collector_user
 public | tokens              | table | gecko_terminal_collector_user
 public | trades              | table | gecko_terminal_collector_user
 public | watchlist           | table | gecko_terminal_collector_user
(9 rows)

# SELECT data from available tables:



# Wait & Patience... this is scheduled to run every 10 minutes, 30 minutes and hourly.

gecko_collector=# SELECT * FROM collection_metadata;
 id |  collector_type  |           last_run            |         last_success          | run_count | error_count | last_error | metadata_json |          created_at           |          updated_at
----+------------------+-------------------------------+-------------------------------+-----------+-------------+------------+---------------+-------------------------------+-------------------------------
  1 | top_pools_solana | 2025-09-26 09:46:10.445297+00 | 2025-09-26 09:46:10.445297+00 |         1 |           0 |            | {}            | 2025-09-26 09:46:11.983294+00 | 2025-09-26 09:46:11.983294+00
(1 row)


gecko_collector=# SELECT * FROM watchlist;
 id |                       pool_id                       |  token_symbol   |   token_name    |               network_address                | is_active |          created_at           |          updated_at           | metadata_json
----+-----------------------------------------------------+-----------------+-----------------+----------------------------------------------+-----------+-------------------------------+-------------------------------+---------------
  1 | solana_F5vAiFCP82RQetoxK7ax4dNQCwqk2yez6aisAbFPenJ2 | Butterfly / SOL | Butterfly / SOL | 4Ds7cxJ82gm34gV22zo2LjPdX3nFbQk9PXK7mjX4pump | t         | 2025-09-26 09:40:32.916554+00 | 2025-09-26 09:40:32.916554+00 | {}
(1 row)






# TODO

# Configure as System Service, tweak collection intervals









# Observed Bugs:

2025-09-26 10:21:10,832 - gecko_terminal_collector.collectors.base.NewPoolsCollector - ERROR - Error ensuring pool exists for solana_DzNHbC9N4eZd9Yab6QfZfAxmXBRNoSrFboLvzyufxU2c: 'latin-1' codec can't encode characters in position 0-2: ordinal not in range(256)
2025-09-26 10:21:10,835 - gecko_terminal_collector.database.sqlalchemy_manager - ERROR - Error storing new pools history record: 'latin-1' codec can't encode characters in position 0-2: ordinal not in range(256)
2025-09-26 10:21:10,835 - gecko_terminal_collector.collectors.base.NewPoolsCollector - ERROR - Error storing history record for solana_DzNHbC9N4eZd9Yab6QfZfAxmXBRNoSrFboLvzyufxU2c: 'latin-1' codec can't encode characters in position 0-2: ordinal not in range(256)
2025-09-26 10:21:10,835 - gecko_terminal_collector.collectors.base.NewPoolsCollector - ERROR - Error processing pool solana_DzNHbC9N4eZd9Yab6QfZfAxmXBRNoSrFboLvzyufxU2c: 'latin-1' codec can't encode characters in position 0-2: ordinal not in range(256)
2025-09-26 10:21:10,842 - gecko_terminal_collector.collectors.base.NewPoolsCollector - ERROR - Error ensuring pool exists for solana_3ibg5GiKe3BTLbJZW4JfPtZvjJ4GCtCsNqZUAb3c2nPa: 'latin-1' codec can't encode characters in position 0-2: ordinal not in range(256)
2025-09-26 10:21:10,845 - gecko_terminal_collector.database.sqlalchemy_manager - ERROR - Error storing new pools history record: 'latin-1' codec can't encode characters in position 0-2: ordinal not in range(256)














