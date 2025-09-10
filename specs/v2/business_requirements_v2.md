

## KIRO_TODO_10 ##

Please review the test coverage in tests/test_base_collector.py to see existing errors, and how the other related fixed might be related. Previous log files suggest that API Limits from the provider are the root cause.

## END_KIRO_TODO_10 ##



## KIRO_TODO_9 ##

I notice while testing that the following tables aren't populating with data correctly:

collection_metadata
execution_history
performance_metrics

system_alerts (in the event of geckoterminal api limits being reached -- it appears to be a problem with the number of API requests over a 24 hour period)



ohlcv data is not being captured


## END_KIRO_TODO_9 ##




## KIRO_TODO_8 ##
Test coverage alignment. I noticed during preliminary testing of:

python examples/cli_with_scheduler.py run-once

that the Rate Limiter backoff logic did not work. This looks like a great script to center core functionality and end-to-end testing on.

please also refer to the following test scripts that were developed along the way:

test_ohlcv_debug.py
test_ohlcv_parsing.py
test_pool_debug.py
test_pool_detailed.py
test_symbol_generation.py
test_workflow_validation.py

## END_KIRO_TODO_8 ##




## KIRO_TODO_3 -- resolve dict/list/dataframe issues [DONE]

# resolving this issue was accomplished by reverting the fixes made to address test coverage, see the following two git diffs:

3edafb684c8636a25d08994b552ae90340b3dbee.patch
68725ca73e666d6d03ff1045d4f69d621fe7988d.patch

# this interesting scenario created a problem where the CLI instance of geckoterminal_collector stopped working, but the test coverage did work. See below an output log:

(C:\Projects\geckoterminal_collector\.conda) C:\Projects\geckoterminal_collector>python examples/cli_with_scheduler.py run-once
2025-09-10 03:58:19,985 - __main__ - INFO - Initializing collection system...
---
DatabaseConfig(url='sqlite:///gecko_data.db', async_url=None, pool_size=10, max_overflow=20, echo=False, timeout=30)
---
2025-09-10 03:58:20,005 - gecko_terminal_collector.database.connection - INFO - Database connection initialized
2025-09-10 03:58:20,005 - gecko_terminal_collector.database.connection - INFO - Creating database tables 
2025-09-10 03:58:20,018 - gecko_terminal_collector.database.connection - INFO - Database tables created successfully
2025-09-10 03:58:20,018 - gecko_terminal_collector.database.sqlalchemy_manager - INFO - SQLAlchemy database manager initialized
2025-09-10 03:58:20,018 - gecko_terminal_collector.monitoring.collection_monitor - INFO - Collection monitor initialized
2025-09-10 03:58:20,018 - gecko_terminal_collector.scheduling.scheduler - INFO - Collection scheduler initialized with monitoring
2025-09-10 03:58:20,018 - __main__ - INFO - Registering collectors...
2025-09-10 03:58:20,018 - gecko_terminal_collector.collectors.base - INFO - Registered collector: dex_monitoring_solana
2025-09-10 03:58:20,018 - gecko_terminal_collector.scheduling.scheduler - INFO - Registered collector dex_monitoring_solana with interval 1h
2025-09-10 03:58:20,029 - gecko_terminal_collector.collectors.base - INFO - Registered collector: top_pools_solana
2025-09-10 03:58:20,029 - gecko_terminal_collector.scheduling.scheduler - INFO - Registered collector top_pools_solana with interval 1h
---
- init watchlist monitor-
---
2025-09-10 03:58:20,029 - gecko_terminal_collector.collectors.base - INFO - Registered collector: watchlist_monitor
2025-09-10 03:58:20,029 - gecko_terminal_collector.scheduling.scheduler - INFO - Registered collector watchlist_monitor with interval 1h
---
- init collector -
---
2025-09-10 03:58:20,030 - gecko_terminal_collector.collectors.base - INFO - Registered collector: watchlist_collector
2025-09-10 03:58:20,030 - gecko_terminal_collector.scheduling.scheduler - INFO - Registered collector watchlist_collector with interval 1h
2025-09-10 03:58:20,030 - gecko_terminal_collector.collectors.base - INFO - Registered collector: ohlcv_collector
2025-09-10 03:58:20,030 - gecko_terminal_collector.scheduling.scheduler - INFO - Registered collector ohlcv_collector with interval 1h
2025-09-10 03:58:20,030 - gecko_terminal_collector.collectors.base - INFO - Registered collector: trade_collector
2025-09-10 03:58:20,030 - gecko_terminal_collector.scheduling.scheduler - INFO - Registered collector trade_collector with interval 30m
2025-09-10 03:58:20,030 - gecko_terminal_collector.collectors.base - INFO - Registered collector: historical_ohlcv_collector
2025-09-10 03:58:20,030 - gecko_terminal_collector.scheduling.scheduler - INFO - Registered collector historical_ohlcv_collector with interval 1d
2025-09-10 03:58:20,031 - __main__ - INFO - Registered 7 collectors
2025-09-10 03:58:20,031 - __main__ - INFO - Initialization completed
-run_collector--
['collector_dex_monitoring_solana', 'collector_top_pools_solana', 'collector_watchlist_monitor', 'collector_watchlist_collector', 'collector_ohlcv_collector', 'collector_trade_collector', 'collector_historical_ohlcv_collector']
---
-collector_status--
job_id:  collector_dex_monitoring_solana
collector:  dex_monitoring_solana
collector_key:  dex_monitoring_solana
---
dex_monitoring_solana
2025-09-10 03:58:20,032 - __main__ - INFO - Running collector 'dex_monitoring_solana' once...
2025-09-10 03:58:20,032 - gecko_terminal_collector.scheduling.scheduler - INFO - Executing collector dex_monitoring_solana on demand
2025-09-10 03:58:20,032 - gecko_terminal_collector.collectors.dex_monitoring - INFO - Starting DEX monitoring collection for network: solana
2025-09-10 03:58:20,654 - httpx - INFO - HTTP Request: GET https://api.geckoterminal.com/api/v2/networks/solana/dexes "HTTP/1.1 200 OK"
-_DEXMonitoringCollector--
<class 'pandas.core.frame.DataFrame'>
---
2025-09-10 03:58:20,662 - gecko_terminal_collector.collectors.dex_monitoring - ERROR - DEX data validation failed: ['DEX data must be a list']
2025-09-10 03:58:20,662 - gecko_terminal_collector.utils.metadata - INFO - Updated metadata for dex_monitoring_solana: Success rate: 0.0%, Total runs: 1, Records collected: 0
2025-09-10 03:58:20,662 - __main__ - INFO - Execution completed:
2025-09-10 03:58:20,662 - __main__ - INFO -   Success: False
2025-09-10 03:58:20,662 - __main__ - INFO -   Records: 0
2025-09-10 03:58:20,662 - __main__ - ERROR -   Errors: DEX data must be a list
2025-09-10 03:58:20,662 - __main__ - INFO - Shutting down collection system...
2025-09-10 03:58:20,664 - gecko_terminal_collector.scheduling.scheduler - WARNING - Scheduler not running, current state: SchedulerState.STOPPED
2025-09-10 03:58:20,664 - __main__ - INFO - Scheduler stopped
2025-09-10 03:58:20,669 - gecko_terminal_collector.database.connection - INFO - Synchronous database engine disposed
2025-09-10 03:58:20,669 - gecko_terminal_collector.database.sqlalchemy_manager - INFO - SQLAlchemy database manager closed
2025-09-10 03:58:20,669 - __main__ - INFO - Database connections closed
2025-09-10 03:58:20,669 - __main__ - INFO - Shutdown completed

(C:\Projects\geckoterminal_collector\.conda) C:\Projects\geckoterminal_collector>
(C:\Projects\geckoterminal_collector\.conda) C:\Projects\geckoterminal_collector>python -m pytest tests/test_dex_monitoring_collector.py::TestDEXMonitoringCollector::test_collect_success -v -s
========================================= test session starts ==========================================
platform win32 -- Python 3.11.13, pytest-8.4.1, pluggy-1.6.0 -- C:\Projects\geckoterminal_collector\.conda\python.exe
cachedir: .pytest_cache
rootdir: C:\Projects\geckoterminal_collector
configfile: pytest.ini
plugins: anyio-4.10.0, asyncio-1.1.0, cov-6.2.1, mock-3.14.1
asyncio: mode=Mode.STRICT, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 1 item                                                                                        

tests/test_dex_monitoring_collector.py::TestDEXMonitoringCollector::test_collect_success -MockGeckoTerminalClient--
[{'id': 'raydium', 'type': 'dex', 'name': 'Raydium'}, {'id': 'orca', 'type': 'dex', 'name': 'Orca'}, {'id': 'raydium-clmm', 'type': 'dex', 'name': 'Raydium (CLMM)'}, {'id': 'fluxbeam', 'type': 'dex', 'name': 'FluxBeam'}, {'id': 'meteora', 'type': 'dex', 'name': 'Meteora'}, {'id': 'dexlab', 'type': 'dex', 'name': 'Dexlab'}, {'id': 'daos-fun', 'type': 'dex', 'name': 'Daos.fun'}, {'id': 'pumpswap', 'type': 'dex', 'name': 'PumpSwap'}, {'id': 'virtuals-solana', 'type': 'dex', 'name': 'Virtuals (Solana)'}, {'id': 'boop-fun', 'type': 'dex', 'name': 'Boop.fun'}, {'id': 'saros-amm', 'type': 'dex', 'name': 'Saros AMM'}, {'id': 'meteora-dbc', 'type': 'dex', 'name': 'Meteora DBC'}, {'id': 'byreal', 'type': 'dex', 'name': 'Byreal'}, {'id': 'pancakeswap-v3-solana', 'type': 'dex', 'name': 'Pancakeswap V3 (Solana)'}, {'id': 'meteora-damm-v2', 'type': 'dex', 'name': 'Meteora DAMM V2'}, {'id': 'raydium-launchlab', 'type': 'dex', 'name': 'Raydium Launchlab'}, {'id': 'pump-fun', 'type': 'dex', 'name': 'Pump.fun'}, {'id': 'saros-dlmm', 'type': 'dex', 'name': 'Saros DLMM'}, {'id': 'wavebreak', 'type': 'dex', 'name': 'Wavebreak'}, {'id': 'heaven', 'type': 'dex', 'name': 'Heaven'}]
---
-_DEXMonitoringCollector--
<class 'list'>
---
-_validate_specific_data--
{'name': 'Heaven'}
---
-_validate_specific_data--
{'name': 'PumpSwap'}
---
-_validate_specific_data--
{'name': 'Raydium'}
---
-_test_collect_success--
CollectionResult(success=True, records_collected=2, errors=[], collection_time=datetime.datetime(2025, 9, 10, 4, 2, 3, 416968), collector_type='dex_monitoring_solana', metadata=None)
---
PASSED

=========================================== warnings summary =========================================== 
.conda\Lib\site-packages\_pytest\cacheprovider.py:475
  C:\Projects\geckoterminal_collector\.conda\Lib\site-packages\_pytest\cacheprovider.py:475: PytestCacheWarning: could not create cache path C:\Projects\geckoterminal_collector\.pytest_cache\v\cache\nodeids: [WinError 5] Access is denied: 'C:\\Projects\\geckoterminal_collector\\.pytest_cache\\v\\cache'
    config.cache.set("cache/nodeids", sorted(self.cached_nodeids))

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
===================================== 1 passed, 1 warning in 0.84s ===================================== 

## END_KIRO_TODO_3 ##



## KIRO_TODO_7 ##
Consistency with "response_to_dict" method. In some cases, things like "data" and "attributes" are expected to use a dict structure. I've performed a variety of fixes to the test coverage which are illustrated in the following git diff:

# these two patch files describe an issue I'm seeing the existing test coverage:
3edafb684c8636a25d08994b552ae90340b3dbee.patch
68725ca73e666d6d03ff1045d4f69d621fe7988d.patch

# other related fixes I've performed as described in the following patch files:
32bcbaa10314db7ab0a98f76ccfe50342dc8f6b0.patch
1fb27ad362c59b955e163c449c0b8099edbeffef.patch
104269c561a09d2595df9bd0e75538799d798aa7.patch
0959e0360e7449b85adf687a3d4f0ae6877b8a1d.patch
f9caa837bbe7b8d11ab79beda0599decd7670b3c.patch
7eea003dbf19bec5f0aeed197132a672b54b2e53.patch

The root cause of this problem is a miscommunication in the early phases of development, where CSV Fixture files are centered around Pandas Dataframes, whereas best practices utilize JSON fixtures. Please see if you can find other areas of the codebase which might be affected.

## END_KIRO_TODO_7 ##


























## DELEGATED ITEMS ##

## KIRO_TODO_6 ##

Please review previously generated system documentation and align with current methods and processes.

## END_KIRO_TODO_6 ##


## KIRO_TODO_5 ##

Please remove all emojis from project, in this context they are unnecessary and produce undesired effects when developing on Windows. Please create a summary of these findings so I may report an issue on github.

## END_KIRO_TODO_5 ##


## KIRO_TODO_4 ##

I've noticed that log files are not being saved in the /logs folder, but instead are being scattered at the root of this project.

I am currently using Windows as a development environment, which I suspect is the source of testing and development issues I've noticed along the way.

## END_KIRO_TODO_4 ##







## COMPLETED ITEMS ##

## TODO_1 - Requirement 1 [DONE] **REQUIREMENT_1**
- Describe updated process for fetching pool data and storing historical records. 

Resolves: Foreign Key / Primary Key constraint that is preventing insertion of records and other problems.
## END_TODO_1 ##

## TODO_2 - Requirement 2 [DONE]
- The existing SDK already provides a method to maintain cryptographic address case-sensitivity requirements for QLib integration.
- Reverse mapping is still useful as many external APIs and tools map to lowercase.

Resolves: Identify what part of the process Kiro got stuck exporting data to QLib. **case_sensitivity_issue** **reverse_lookup**
## END_TODO_2 ##


## Requirement 1: **REQUIREMENT_1**

# Process:
- Fetch new pools using get_new_pools_by_network() SDK call on a scheduled basis. This is a new method, which is similar to get_new_pools_by_network_dex(). The goal of this updated SDK call is to accomplish two things:

1. Populate the "Pools" table prior to making any other database requests, the foreign key constraints on this table make it effectively the "Fact Table" in a star schema which I believe is in use here.
2. Leverage additional information already contained in this API response to aid in predictive modeling.

# SDK:
await client.get_new_pools_by_network("solana")

# CSV Fixture
get_new_pools_by_network.csv

# Populate Pools table with this information to resolve Foreign Key constraint, for example:
id: solana_jbZxBTj6DKvTzjLSHN1ZTgj1Ef7f7n7ZunopXvGVNrU
address: jbZxBTj6DKvTzjLSHN1ZTgj1Ef7f7n7ZunopXvGVNrU
name: "TTT / SOL"
dex_id: "pumpswap"
base_token_id: solana_9oZzjkRV6bjKP5EHnnavgNkjj55LTn9gKNkeZiXepump
quote_token_id: So11111111111111111111111111111111111111112
reserve_usd: 4943.8875
created_at: "2025-09-08T20:09:26Z"
last_updated: 

# Create new table to create historic records of get_new_pools_by_network, for example:
id: "solana_jbZxBTj6DKvTzjLSHN1ZTgj1Ef7f7n7ZunopXvGVNrU"
type: "pool"
name: "TTT / SOL"
base_token_price_usd: "0.00000624"
base_token_price_native_currency: "0.00000003"
quote_token_price_usd: "215.4862309"
quote_token_price_native_currency: "1"
address: "jbZxBTj6DKvTzjLSHN1ZTgj1Ef7f7n7ZunopXvGVNrU"
reserve_in_usd: "4943.8875"
pool_created_at: "2025-09-09T21:27:52Z"
fdv_usd: "6235.663542"
market_cap_usd:
price_change_percentage_h1: "1.758"
price_change_percentage_h24: "1.758"
transactions_h1_buys: "5"
transactions_h1_sells: "4"
transactions_h24_buys: "5"
transactions_h24_sells: "4"
volume_usd_h24: "793.735054"
dex_id: "pump-fun"
base_token_id: "solana_9oZzjkRV6bjKP5EHnnavgNkjj55LTn9gKNkeZiXepump"
quote_token_id: "solana_So11111111111111111111111111111111111111112"

## End Requirement 1




## Requirement 2 [DONE] **REQUIREMENT_2**
Export data into QLib compatible bin file.

QLib bin files are imported into QLib-Server (the intended target for this data) using incremental imports which is modeled after the scripts/dump_bin.py script. These are stored as "bin" files which are basically a stack of buffers for each column of data.

See ./examples/qlib_scripts/dump_bin.py for the complete process. 

# Working example of this process:
python scripts/dump_bin.py dump_all --csv_path /Projects/wave_rider_qlib/csv_data/geckoterminal_output --qlib_dir /Projects/wave_rider_qlib/qlib_data/TESTDATA --date_field_name datetime --freq 60min --symbol_field_name symbol --include_fields open,high,low,close,volume

# This then allows for the data to be referenced using the following methodology:
provider_uri = "/Projects/wave_rider_qlib/qlib_data/TESTDATA"
qlib.init(provider_uri=provider_uri, region=REG_US)

## Technical Details:

# QLib bin files follow a very simple methodology which is outlined in the following code sample:
date_index = self.get_datetime_index(_df, calendar_list)
for field in self.get_dump_fields(_df.columns):
    bin_path = features_dir.joinpath(f"{field.lower()}.{self.freq}{self.DUMP_FILE_SUFFIX}")
    if field not in _df.columns:
        continue
    if bin_path.exists() and self._mode == self.UPDATE_MODE:
        # update
        with bin_path.open("ab") as fp:
            np.array(_df[field]).astype("<f").tofile(fp)
    else:
        # append; self._mode == self.ALL_MODE or not bin_path.exists()
        np.hstack([date_index, _df[field]]).astype("<f").tofile(str(bin_path.resolve()))

# QLib contains a helper class that can be used to check the "Health" status of created bin files, see ./examples/qlib_scripts/check_data_health.py. This Class could be utilized as a useful QA method, and is included below for reference.

class DataHealthChecker:
    """Checks a dataset for data completeness and correctness. The data will be converted to a pd.DataFrame and checked for the following problems:
    - any of the columns ["open", "high", "low", "close", "volume"] are missing
    - any data is missing
    - any step change in the OHLCV columns is above a threshold (default: 0.5 for price, 3 for volume)
    - any factor is missing
    """

    def __init__(
        self,
        csv_path=None,
        qlib_dir=None,
        freq="day",
        large_step_threshold_price=0.5,
        large_step_threshold_volume=3,
        missing_data_num=0,
    ):
        assert csv_path or qlib_dir, "One of csv_path or qlib_dir should be provided."
        assert not (csv_path and qlib_dir), "Only one of csv_path or qlib_dir should be provided."

        self.data = {}
        self.problems = {}
        self.freq = freq
        self.large_step_threshold_price = large_step_threshold_price
        self.large_step_threshold_volume = large_step_threshold_volume
        self.missing_data_num = missing_data_num

        if csv_path:
            assert os.path.isdir(csv_path), f"{csv_path} should be a directory."
            files = [f for f in os.listdir(csv_path) if f.endswith(".csv")]
            for filename in tqdm(files, desc="Loading data"):
                df = pd.read_csv(os.path.join(csv_path, filename))
                self.data[filename] = df

        elif qlib_dir:
            qlib.init(provider_uri=qlib_dir)
            self.load_qlib_data()

    def load_qlib_data(self):
        instruments = D.instruments(market="all")
        instrument_list = D.list_instruments(instruments=instruments, as_list=True, freq=self.freq)
        required_fields = ["$open", "$close", "$low", "$high", "$volume", "$factor"]
        for instrument in instrument_list:
            df = D.features([instrument], required_fields, freq=self.freq)
            df.rename(
                columns={
                    "$open": "open",
                    "$close": "close",
                    "$low": "low",
                    "$high": "high",
                    "$volume": "volume",
                    "$factor": "factor",
                },
                inplace=True,
            )
            self.data[instrument] = df
        print(df)

    def check_missing_data(self) -> Optional[pd.DataFrame]:
        """Check if any data is missing in the DataFrame."""
        result_dict = {
            "instruments": [],
            "open": [],
            "high": [],
            "low": [],
            "close": [],
            "volume": [],
        }
        for filename, df in self.data.items():
            missing_data_columns = df.isnull().sum()[df.isnull().sum() > self.missing_data_num].index.tolist()
            if len(missing_data_columns) > 0:
                result_dict["instruments"].append(filename)
                result_dict["open"].append(df.isnull().sum()["open"])
                result_dict["high"].append(df.isnull().sum()["high"])
                result_dict["low"].append(df.isnull().sum()["low"])
                result_dict["close"].append(df.isnull().sum()["close"])
                result_dict["volume"].append(df.isnull().sum()["volume"])

        result_df = pd.DataFrame(result_dict).set_index("instruments")
        if not result_df.empty:
            return result_df
        else:
            logger.info(f"There are no missing data.")
            return None

    def check_large_step_changes(self) -> Optional[pd.DataFrame]:
        """Check if there are any large step changes above the threshold in the OHLCV columns."""
        result_dict = {
            "instruments": [],
            "col_name": [],
            "date": [],
            "pct_change": [],
        }
        for filename, df in self.data.items():
            affected_columns = []
            for col in ["open", "high", "low", "close", "volume"]:
                if col in df.columns:
                    pct_change = df[col].pct_change(fill_method=None).abs()
                    threshold = self.large_step_threshold_volume if col == "volume" else self.large_step_threshold_price
                    if pct_change.max() > threshold:
                        large_steps = pct_change[pct_change > threshold]
                        result_dict["instruments"].append(filename)
                        result_dict["col_name"].append(col)
                        result_dict["date"].append(large_steps.index.to_list()[0][1].strftime("%Y-%m-%d"))
                        result_dict["pct_change"].append(pct_change.max())
                        affected_columns.append(col)

        result_df = pd.DataFrame(result_dict).set_index("instruments")
        if not result_df.empty:
            return result_df
        else:
            logger.info(f"There are no large step changes in the OHLCV column above the threshold.")
            return None

    def check_required_columns(self) -> Optional[pd.DataFrame]:
        """Check if any of the required columns (OLHCV) are missing in the DataFrame."""
        required_columns = ["open", "high", "low", "close", "volume"]
        result_dict = {
            "instruments": [],
            "missing_col": [],
        }
        for filename, df in self.data.items():
            if not all(column in df.columns for column in required_columns):
                missing_required_columns = [column for column in required_columns if column not in df.columns]
                result_dict["instruments"].append(filename)
                result_dict["missing_col"] += missing_required_columns

        result_df = pd.DataFrame(result_dict).set_index("instruments")
        if not result_df.empty:
            return result_df
        else:
            logger.info(f"The columns (OLHCV) are complete and not missing.")
            return None

    def check_missing_factor(self) -> Optional[pd.DataFrame]:
        """Check if the 'factor' column is missing in the DataFrame."""
        result_dict = {
            "instruments": [],
            "missing_factor_col": [],
            "missing_factor_data": [],
        }
        for filename, df in self.data.items():
            if "000300" in filename or "000903" in filename or "000905" in filename:
                continue
            if "factor" not in df.columns:
                result_dict["instruments"].append(filename)
                result_dict["missing_factor_col"].append(True)
            if df["factor"].isnull().all():
                if filename in result_dict["instruments"]:
                    result_dict["missing_factor_data"].append(True)
                else:
                    result_dict["instruments"].append(filename)
                    result_dict["missing_factor_col"].append(False)
                    result_dict["missing_factor_data"].append(True)

        result_df = pd.DataFrame(result_dict).set_index("instruments")
        if not result_df.empty:
            return result_df
        else:
            logger.info(f"The `factor` column already exists and is not empty.")
            return None

    def check_data(self):
        check_missing_data_result = self.check_missing_data()
        check_large_step_changes_result = self.check_large_step_changes()
        check_required_columns_result = self.check_required_columns()
        check_missing_factor_result = self.check_missing_factor()
        if (
            check_large_step_changes_result is not None
            or check_large_step_changes_result is not None
            or check_required_columns_result is not None
            or check_missing_factor_result is not None
        ):
            print(f"\nSummary of data health check ({len(self.data)} files checked):")
            print("-------------------------------------------------")
            if isinstance(check_missing_data_result, pd.DataFrame):
                logger.warning(f"There is missing data.")
                print(check_missing_data_result)
            if isinstance(check_large_step_changes_result, pd.DataFrame):
                logger.warning(f"The OHLCV column has large step changes.")
                print(check_large_step_changes_result)
            if isinstance(check_required_columns_result, pd.DataFrame):
                logger.warning(f"Columns (OLHCV) are missing.")
                print(check_required_columns_result)
            if isinstance(check_missing_factor_result, pd.DataFrame):
                logger.warning(f"The factor column does not exist or is empty")
                print(check_missing_factor_result)

## End Requirement 2