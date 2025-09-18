"""
QLib Integration Module for New Pools History Data

This module provides functionality to export new pools history data
in QLib-compatible format for quantitative analysis and model training.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import logging
from pathlib import Path
import json

from sqlalchemy import text
from gecko_terminal_collector.database.manager import DatabaseManager

logger = logging.getLogger(__name__)


class QLibDataExporter:
    """
    Export new pools history data in QLib-compatible format.
    
    QLib expects data in specific formats:
    - Time series data with datetime index
    - Feature columns with standardized names
    - Proper handling of missing values
    - Normalized price and volume data
    """
    
    def __init__(self, db_manager: DatabaseManager, output_dir: str = "./qlib_data"):
        self.db_manager = db_manager
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # QLib feature mapping
        self.feature_mapping = {
            # Price features
            'open': 'open_price_usd',
            'high': 'high_price_usd', 
            'low': 'low_price_usd',
            'close': 'close_price_usd',
            'volume': 'volume_usd_h24',
            
            # Technical indicators
            'rsi': 'relative_strength_index',
            'macd': 'moving_average_convergence',
            'volatility': 'volatility_score',
            
            # Market structure
            'liquidity': 'reserve_in_usd',
            'market_cap': 'market_cap_usd',
            'fdv': 'fdv_usd',
            
            # Activity metrics
            'transactions': 'transactions_h24_buys',
            'activity_score': 'activity_score',
            'signal_score': 'signal_score',
            
            # Price changes
            'return_1h': 'price_change_percentage_h1',
            'return_24h': 'price_change_percentage_h24'
        }
    
    async def export_training_data(
        self,
        start_date: datetime,
        end_date: datetime,
        networks: List[str] = None,
        min_liquidity_usd: float = 1000,
        min_volume_usd: float = 100,
        export_name: str = None
    ) -> Dict[str, Any]:
        """
        Export training data for QLib models.
        
        Args:
            start_date: Start date for data export
            end_date: End date for data export
            networks: List of networks to include (None for all)
            min_liquidity_usd: Minimum liquidity threshold
            min_volume_usd: Minimum volume threshold
            export_name: Name for the export (auto-generated if None)
            
        Returns:
            Dictionary with export metadata
        """
        try:
            if not export_name:
                export_name = f"training_data_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
            
            logger.info(f"Starting QLib training data export: {export_name}")
            
            # Get raw data from database
            raw_data = await self._fetch_history_data(
                start_date, end_date, networks, min_liquidity_usd, min_volume_usd
            )
            
            if raw_data.empty:
                logger.warning("No data found for specified criteria")
                return {'success': False, 'error': 'No data found'}
            
            # Process data for QLib format
            qlib_data = self._process_for_qlib(raw_data)
            
            # Generate features
            feature_data = self._generate_features(qlib_data)
            
            # Create labels (target variables)
            labeled_data = self._create_labels(feature_data)
            
            # Split into train/validation/test sets
            datasets = self._split_datasets(labeled_data)
            
            # Save datasets
            export_paths = await self._save_datasets(datasets, export_name)
            
            # Create QLib configuration
            qlib_config = self._create_qlib_config(datasets, export_name)
            
            # Save configuration
            config_path = self.output_dir / f"{export_name}_config.json"
            with open(config_path, 'w') as f:
                json.dump(qlib_config, f, indent=2, default=str)
            
            # Record export metadata
            export_metadata = {
                'success': True,
                'export_name': export_name,
                'start_date': start_date,
                'end_date': end_date,
                'total_records': len(labeled_data),
                'unique_pools': labeled_data['pool_id'].nunique(),
                'networks': networks or 'all',
                'export_paths': export_paths,
                'config_path': str(config_path),
                'created_at': datetime.now()
            }
            
            await self._record_export_metadata(export_metadata)
            
            logger.info(f"QLib export completed: {export_name}")
            return export_metadata
            
        except Exception as e:
            logger.error(f"Error exporting QLib training data: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _fetch_history_data(
        self,
        start_date: datetime,
        end_date: datetime,
        networks: List[str] = None,
        min_liquidity_usd: float = 1000,
        min_volume_usd: float = 100
    ) -> pd.DataFrame:
        """Fetch history data from database."""
        try:
            # Build query
            query = """
            SELECT 
                pool_id,
                timestamp,
                datetime,
                collection_interval,
                network_id,
                dex_id,
                qlib_symbol,
                
                -- Price data
                open_price_usd,
                high_price_usd,
                low_price_usd,
                close_price_usd,
                
                -- Volume and liquidity
                volume_usd_h24,
                volume_usd_h1,
                reserve_in_usd,
                liquidity_depth_usd,
                
                -- Market metrics
                market_cap_usd,
                fdv_usd,
                
                -- Price changes
                price_change_percentage_h1,
                price_change_percentage_h24,
                price_change_percentage_interval,
                
                -- Trading activity
                transactions_h24_buys,
                transactions_h24_sells,
                transactions_h1_buys,
                transactions_h1_sells,
                buy_sell_ratio_h24,
                
                -- Technical indicators
                relative_strength_index,
                moving_average_convergence,
                trend_strength,
                volatility_score,
                
                -- Signal analysis
                signal_score,
                activity_score,
                momentum_indicator,
                
                -- Pool characteristics
                pool_age_hours,
                is_new_pool,
                data_quality_score,
                
                -- QLib features
                qlib_features_json
                
            FROM new_pools_history_enhanced
            WHERE datetime >= :start_date 
                AND datetime <= :end_date
                AND reserve_in_usd >= :min_liquidity
                AND volume_usd_h24 >= :min_volume
                AND data_quality_score >= 50
            """
            
            params = {
                'start_date': start_date,
                'end_date': end_date,
                'min_liquidity': min_liquidity_usd,
                'min_volume': min_volume_usd
            }
            
            # Add network filter if specified
            if networks:
                query += " AND network_id = ANY(:networks)"
                params['networks'] = networks
            
            query += " ORDER BY pool_id, datetime"
            
            # Execute query
            with self.db_manager.connection.get_session() as session:
                result = session.execute(text(query), params)
                data = result.fetchall()
                
                if not data:
                    return pd.DataFrame()
                
                # Convert to DataFrame
                columns = result.keys()
                df = pd.DataFrame(data, columns=columns)
                
                return df
                
        except Exception as e:
            logger.error(f"Error fetching history data: {e}")
            return pd.DataFrame()
    
    def _process_for_qlib(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        """Process raw data for QLib format."""
        try:
            df = raw_data.copy()
            
            # Convert datetime column to proper datetime type
            df['datetime'] = pd.to_datetime(df['datetime'])
            
            # Set datetime as index
            df.set_index('datetime', inplace=True)
            
            # Sort by pool_id and datetime
            df.sort_values(['pool_id', 'datetime'], inplace=True)
            
            # Handle missing values
            numeric_columns = df.select_dtypes(include=[np.number]).columns
            df[numeric_columns] = df[numeric_columns].fillna(method='ffill').fillna(0)
            
            # Normalize price data (convert to returns)
            price_columns = ['open_price_usd', 'high_price_usd', 'low_price_usd', 'close_price_usd']
            for col in price_columns:
                if col in df.columns:
                    df[f'{col}_return'] = df.groupby('pool_id')[col].pct_change()
            
            # Log-transform volume data
            volume_columns = ['volume_usd_h24', 'volume_usd_h1', 'reserve_in_usd']
            for col in volume_columns:
                if col in df.columns:
                    df[f'{col}_log'] = np.log1p(df[col])
            
            # Create QLib-compatible symbol column
            df['symbol'] = df['qlib_symbol'].fillna(df['pool_id'])
            
            return df
            
        except Exception as e:
            logger.error(f"Error processing data for QLib: {e}")
            return pd.DataFrame()
    
    def _generate_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Generate additional features for ML models."""
        try:
            df = data.copy()
            
            # Technical indicators
            for pool_id in df['pool_id'].unique():
                pool_mask = df['pool_id'] == pool_id
                pool_data = df[pool_mask].copy()
                
                if len(pool_data) < 10:  # Need minimum data points
                    continue
                
                # Moving averages
                if 'close_price_usd' in pool_data.columns:
                    pool_data['ma_5'] = pool_data['close_price_usd'].rolling(5).mean()
                    pool_data['ma_20'] = pool_data['close_price_usd'].rolling(20).mean()
                    pool_data['ma_ratio'] = pool_data['ma_5'] / pool_data['ma_20']
                
                # Volume indicators
                if 'volume_usd_h24' in pool_data.columns:
                    pool_data['volume_ma_5'] = pool_data['volume_usd_h24'].rolling(5).mean()
                    pool_data['volume_ratio'] = pool_data['volume_usd_h24'] / pool_data['volume_ma_5']
                
                # Volatility
                if 'close_price_usd_return' in pool_data.columns:
                    pool_data['volatility_5'] = pool_data['close_price_usd_return'].rolling(5).std()
                    pool_data['volatility_20'] = pool_data['close_price_usd_return'].rolling(20).std()
                
                # Update main dataframe
                df.loc[pool_mask, pool_data.columns] = pool_data
            
            # Cross-sectional features
            df['volume_rank'] = df.groupby(df.index)['volume_usd_h24'].rank(pct=True)
            df['liquidity_rank'] = df.groupby(df.index)['reserve_in_usd'].rank(pct=True)
            df['signal_rank'] = df.groupby(df.index)['signal_score'].rank(pct=True)
            
            return df
            
        except Exception as e:
            logger.error(f"Error generating features: {e}")
            return data
    
    def _create_labels(self, data: pd.DataFrame) -> pd.DataFrame:
        """Create target labels for supervised learning."""
        try:
            df = data.copy()
            
            # Forward returns as labels
            for pool_id in df['pool_id'].unique():
                pool_mask = df['pool_id'] == pool_id
                pool_data = df[pool_mask].copy()
                
                if 'close_price_usd' in pool_data.columns:
                    # Calculate forward returns
                    pool_data['label_return_1h'] = pool_data['close_price_usd'].pct_change(periods=-1)
                    pool_data['label_return_4h'] = pool_data['close_price_usd'].pct_change(periods=-4)
                    pool_data['label_return_24h'] = pool_data['close_price_usd'].pct_change(periods=-24)
                    
                    # Binary classification labels
                    pool_data['label_up_1h'] = (pool_data['label_return_1h'] > 0).astype(int)
                    pool_data['label_up_4h'] = (pool_data['label_return_4h'] > 0).astype(int)
                    pool_data['label_up_24h'] = (pool_data['label_return_24h'] > 0).astype(int)
                    
                    # Volatility labels
                    pool_data['label_high_vol'] = (pool_data['label_return_1h'].abs() > 0.05).astype(int)
                
                # Volume surge labels
                if 'volume_usd_h24' in pool_data.columns:
                    volume_ma = pool_data['volume_usd_h24'].rolling(24).mean()
                    pool_data['label_volume_surge'] = (pool_data['volume_usd_h24'] > volume_ma * 2).astype(int)
                
                # Update main dataframe
                df.loc[pool_mask, pool_data.columns] = pool_data
            
            return df
            
        except Exception as e:
            logger.error(f"Error creating labels: {e}")
            return data
    
    def _split_datasets(self, data: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """Split data into train/validation/test sets."""
        try:
            # Sort by datetime
            df = data.sort_index()
            
            # Time-based split (70% train, 15% validation, 15% test)
            total_time = df.index.max() - df.index.min()
            train_end = df.index.min() + total_time * 0.7
            val_end = df.index.min() + total_time * 0.85
            
            train_data = df[df.index <= train_end]
            val_data = df[(df.index > train_end) & (df.index <= val_end)]
            test_data = df[df.index > val_end]
            
            logger.info(f"Dataset split - Train: {len(train_data)}, Val: {len(val_data)}, Test: {len(test_data)}")
            
            return {
                'train': train_data,
                'validation': val_data,
                'test': test_data,
                'full': df
            }
            
        except Exception as e:
            logger.error(f"Error splitting datasets: {e}")
            return {'full': data}
    
    async def _save_datasets(self, datasets: Dict[str, pd.DataFrame], export_name: str) -> Dict[str, str]:
        """Save datasets to files."""
        try:
            export_paths = {}
            
            for split_name, data in datasets.items():
                if data.empty:
                    continue
                
                # Save as parquet for efficiency
                file_path = self.output_dir / f"{export_name}_{split_name}.parquet"
                data.to_parquet(file_path)
                export_paths[split_name] = str(file_path)
                
                # Also save as CSV for compatibility
                csv_path = self.output_dir / f"{export_name}_{split_name}.csv"
                data.to_csv(csv_path)
                export_paths[f"{split_name}_csv"] = str(csv_path)
                
                logger.info(f"Saved {split_name} dataset: {len(data)} records to {file_path}")
            
            return export_paths
            
        except Exception as e:
            logger.error(f"Error saving datasets: {e}")
            return {}
    
    def _create_qlib_config(self, datasets: Dict[str, pd.DataFrame], export_name: str) -> Dict:
        """Create QLib configuration for the exported data."""
        try:
            # Get feature columns (exclude metadata and labels)
            full_data = datasets.get('full', pd.DataFrame())
            if full_data.empty:
                return {}
            
            # Define feature columns
            feature_columns = [col for col in full_data.columns 
                             if not col.startswith('label_') 
                             and col not in ['pool_id', 'symbol', 'network_id', 'dex_id']]
            
            # Define label columns
            label_columns = [col for col in full_data.columns if col.startswith('label_')]
            
            config = {
                'data_config': {
                    'name': export_name,
                    'description': f'New pools history data export for QLib - {export_name}',
                    'created_at': datetime.now().isoformat(),
                    'data_path': str(self.output_dir),
                    'symbol_column': 'symbol',
                    'datetime_column': 'datetime'
                },
                'features': {
                    'columns': feature_columns,
                    'count': len(feature_columns),
                    'types': {
                        'price': [col for col in feature_columns if 'price' in col],
                        'volume': [col for col in feature_columns if 'volume' in col],
                        'technical': [col for col in feature_columns if any(x in col for x in ['rsi', 'ma_', 'volatility'])],
                        'fundamental': [col for col in feature_columns if any(x in col for x in ['market_cap', 'fdv', 'liquidity'])]
                    }
                },
                'labels': {
                    'columns': label_columns,
                    'count': len(label_columns),
                    'types': {
                        'returns': [col for col in label_columns if 'return' in col],
                        'binary': [col for col in label_columns if 'up_' in col or 'surge' in col or 'high_vol' in col]
                    }
                },
                'datasets': {
                    split: {
                        'records': len(data),
                        'unique_symbols': data['symbol'].nunique() if 'symbol' in data.columns else 0,
                        'date_range': {
                            'start': data.index.min().isoformat() if not data.empty else None,
                            'end': data.index.max().isoformat() if not data.empty else None
                        }
                    }
                    for split, data in datasets.items()
                },
                'qlib_workflow': {
                    'data_handler': 'Alpha158',  # QLib data handler
                    'model_configs': {
                        'linear': {
                            'class': 'LinearModel',
                            'kwargs': {'estimator': 'ridge'}
                        },
                        'lgb': {
                            'class': 'LGBModel',
                            'kwargs': {}
                        },
                        'transformer': {
                            'class': 'TransformerModel',
                            'kwargs': {'d_model': 64, 'nhead': 4}
                        }
                    }
                }
            }
            
            return config
            
        except Exception as e:
            logger.error(f"Error creating QLib config: {e}")
            return {}
    
    async def _record_export_metadata(self, metadata: Dict) -> None:
        """Record export metadata in database."""
        try:
            from enhanced_new_pools_history_model import QLibDataExport
            
            export_record = QLibDataExport(
                export_name=metadata['export_name'],
                export_type='training',
                start_timestamp=int(metadata['start_date'].timestamp()),
                end_timestamp=int(metadata['end_date'].timestamp()),
                networks=metadata['networks'],
                pool_count=metadata['unique_pools'],
                record_count=metadata['total_records'],
                file_path=str(metadata.get('export_paths', {})),
                status='completed',
                qlib_config_json=metadata.get('config', {}),
                created_at=metadata['created_at'],
                completed_at=datetime.now()
            )
            
            with self.db_manager.connection.get_session() as session:
                session.add(export_record)
                session.commit()
            
            logger.info(f"Recorded export metadata for {metadata['export_name']}")
            
        except Exception as e:
            logger.error(f"Error recording export metadata: {e}")


class QLibModelTrainer:
    """
    Train QLib models using exported new pools data.
    """
    
    def __init__(self, data_path: str):
        self.data_path = Path(data_path)
    
    def create_qlib_workflow(self, config_path: str) -> Dict:
        """Create QLib workflow configuration."""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # QLib workflow template
            workflow = {
                'task': {
                    'model': {
                        'class': 'LGBModel',
                        'module_path': 'qlib.contrib.model.gbdt',
                        'kwargs': {
                            'loss': 'mse',
                            'colsample_bytree': 0.8879,
                            'learning_rate': 0.0421,
                            'subsample': 0.8789,
                            'lambda_l1': 205.6999,
                            'lambda_l2': 580.9768,
                            'max_depth': 8,
                            'num_leaves': 210,
                            'num_threads': 20
                        }
                    },
                    'dataset': {
                        'class': 'DatasetH',
                        'module_path': 'qlib.data.dataset',
                        'kwargs': {
                            'handler': {
                                'class': 'Alpha158',
                                'module_path': 'qlib.contrib.data.handler',
                                'kwargs': {
                                    'start_time': config['datasets']['train']['date_range']['start'],
                                    'end_time': config['datasets']['test']['date_range']['end'],
                                    'fit_start_time': config['datasets']['train']['date_range']['start'],
                                    'fit_end_time': config['datasets']['train']['date_range']['end'],
                                    'instruments': 'all',
                                    'infer_processors': [
                                        {'class': 'RobustZScoreNorm', 'kwargs': {'fields_group': 'feature', 'clip_outlier': True}},
                                        {'class': 'Fillna', 'kwargs': {'fields_group': 'feature'}}
                                    ],
                                    'learn_processors': [
                                        {'class': 'DropnaLabel'},
                                        {'class': 'CSRankNorm', 'kwargs': {'fields_group': 'label'}}
                                    ]
                                }
                            },
                            'segments': {
                                'train': (config['datasets']['train']['date_range']['start'], 
                                         config['datasets']['train']['date_range']['end']),
                                'valid': (config['datasets']['validation']['date_range']['start'], 
                                         config['datasets']['validation']['date_range']['end']),
                                'test': (config['datasets']['test']['date_range']['start'], 
                                        config['datasets']['test']['date_range']['end'])
                            }
                        }
                    }
                },
                'port_analysis_config': {
                    'strategy': {
                        'class': 'TopkDropoutStrategy',
                        'module_path': 'qlib.contrib.strategy.signal_strategy',
                        'kwargs': {
                            'signal': '<PRED>',
                            'topk': 50,
                            'n_drop': 5
                        }
                    },
                    'backtest': {
                        'start_time': config['datasets']['test']['date_range']['start'],
                        'end_time': config['datasets']['test']['date_range']['end'],
                        'account': 100000,
                        'benchmark': None,
                        'exchange_kwargs': {
                            'freq': 'day',
                            'limit_threshold': 0.095,
                            'deal_price': 'close',
                            'open_cost': 0.0005,
                            'close_cost': 0.0015,
                            'min_cost': 5
                        }
                    }
                }
            }
            
            return workflow
            
        except Exception as e:
            logger.error(f"Error creating QLib workflow: {e}")
            return {}


# Usage example and CLI integration
async def export_qlib_data_cli(
    db_manager: DatabaseManager,
    start_date: str,
    end_date: str,
    networks: List[str] = None,
    output_dir: str = "./qlib_data",
    min_liquidity: float = 1000,
    min_volume: float = 100
):
    """CLI function to export QLib data."""
    try:
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        
        exporter = QLibDataExporter(db_manager, output_dir)
        
        result = await exporter.export_training_data(
            start_date=start_dt,
            end_date=end_dt,
            networks=networks,
            min_liquidity_usd=min_liquidity,
            min_volume_usd=min_volume
        )
        
        if result['success']:
            print(f"✅ QLib data export completed: {result['export_name']}")
            print(f"📊 Total records: {result['total_records']}")
            print(f"🏊 Unique pools: {result['unique_pools']}")
            print(f"📁 Output directory: {output_dir}")
        else:
            print(f"❌ Export failed: {result['error']}")
        
        return result
        
    except Exception as e:
        logger.error(f"CLI export error: {e}")
        print(f"❌ Export error: {e}")
        return {'success': False, 'error': str(e)}