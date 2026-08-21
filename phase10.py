#!/usr/bin/env python3
"""
Phase 10 - Historical / Event-Driven Backtest Engine
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent

def write(rel_path: str, content: str):
    path = ROOT / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"written: {rel_path}")

# --------------------------------------------------------------------
# 1. Update config.py with backtest settings
# --------------------------------------------------------------------
write("src/core/config.py", r'''
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List
from enum import Enum

class Mode(str, Enum):
    research = "research"
    paper = "paper"
    live = "live"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Project
    mode: Mode = Mode.research
    live_trading_enabled: bool = False

    # Database
    database_url: str = "sqlite:///data/whale.db"

    # Chain flags
    eth_enabled: bool = True
    bsc_enabled: bool = False
    solana_enabled: bool = False

    # Ethereum
    eth_primary_provider: str = "alchemy"
    eth_backup_provider: str = "etherscan"
    eth_rpc_url: Optional[str] = None
    eth_ws_url: Optional[str] = None
    eth_etherscan_api_key: Optional[str] = None
    eth_etherscan_base_url: str = "https://api.etherscan.io/api"
    eth_chain_id: int = 1
    eth_confirmation_blocks: int = 6
    eth_finality_blocks: int = 20
    eth_request_timeout: int = 30
    eth_max_retries: int = 5
    eth_rate_limit: int = 5
    eth_backfill_batch_size: int = 100
    eth_backfill_resume_file: str = "data/backfill_resume.json"

    # BSC
    bsc_primary_provider: str = "quicknode"
    bsc_backup_provider: str = "bscscan"
    bsc_rpc_url: Optional[str] = None
    bsc_ws_url: Optional[str] = None
    bscscan_api_key: Optional[str] = None
    bsc_chain_id: int = 56

    # Solana
    solana_primary_provider: str = "helius"
    solana_backup_provider: str = "solscan"
    solana_rpc_url: Optional[str] = None
    solana_ws_url: Optional[str] = None
    solana_api_key: Optional[str] = None

    # Whale Detection (Phase 6)
    whale_min_total_volume_usd: float = 1_000_000
    whale_min_avg_trade_usd: float = 50_000
    whale_min_largest_trade_usd: float = 100_000
    whale_min_buy_volume_usd: float = 500_000
    whale_min_swap_count: int = 10
    whale_lookback_days: int = 30
    whale_score_threshold_candidate: float = 60
    whale_score_threshold_whale: float = 80
    whale_volume_weight: float = 0.25
    whale_avg_trade_weight: float = 0.20
    whale_largest_trade_weight: float = 0.20
    whale_activity_weight: float = 0.15
    whale_dex_activity_weight: float = 0.10
    whale_capital_weight: float = 0.10

    # Scoring Weights (for Smart Money later)
    weight_capital: float = 0.15
    weight_volume: float = 0.15
    weight_tx_size: float = 0.15
    weight_consistency: float = 0.10
    weight_roi: float = 0.15
    weight_win_rate: float = 0.15
    weight_entry_timing: float = 0.15

    # Token Universe Filters (not used yet)
    min_liquidity_usd: float = 1_000_000
    min_24h_volume_usd: float = 500_000
    min_market_cap_usd: float = 5_000_000
    min_token_age_days: int = 7
    max_token_age_days: int = 3650
    min_whale_activity_count: int = 3

    # Consensus (Phase 8)
    consensus_window_minutes: int = 60
    min_independent_whales: int = 3
    min_net_flow_usd: float = 500_000
    min_consensus_score: float = 70
    min_consensus_confidence: float = 70

    consensus_weight_independent_count: float = 0.25
    consensus_weight_net_flow: float = 0.20
    consensus_weight_buy_sell_ratio: float = 0.15
    consensus_weight_avg_whale_score: float = 0.10
    consensus_weight_avg_smart_money_score: float = 0.15
    consensus_weight_temporal_convergence: float = 0.10
    consensus_weight_whale_agreement: float = 0.05

    # Signal (Phase 9)
    signal_min_score: float = 70
    signal_min_confidence: float = 70

    signal_weight_whale_consensus: float = 0.25
    signal_weight_smart_money: float = 0.15
    signal_weight_net_whale_flow: float = 0.10
    signal_weight_independent_whales: float = 0.10
    signal_weight_market_confirmation: float = 0.20
    signal_weight_liquidity: float = 0.05
    signal_weight_volume: float = 0.05
    signal_weight_entry_timing: float = 0.05
    signal_weight_market_quality: float = 0.05

    market_confirm_bullish_threshold: float = 60
    market_confirm_bearish_threshold: float = 40
    market_confirm_neutral_min: float = 40
    market_confirm_neutral_max: float = 60

    entry_timing_overbought_rsi: float = 70
    entry_timing_oversold_rsi: float = 30

    min_liquidity_score: float = 50
    min_volume_score: float = 50
    min_volatility_score: float = 40
    max_volatility_score: float = 80

    gate_available_check: bool = True

    required_confirmations: int = 6

    rate_limit_enabled: bool = True
    cost_tracking_enabled: bool = True

    gate_api_key: Optional[str] = None
    gate_api_secret: Optional[str] = None

    buy_confidence_threshold: float = 80
    sell_confidence_threshold: float = 80
    native_asset_symbol: str = "ETH"
    wrapped_native_symbol: str = "WETH"
    wrapped_native_address: str = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
    stablecoin_addresses_ethereum: str = "0xdAC17F958D2ee523a2206206994597C13D831ec7,0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48,0x6B175474E89094C44Da98b954EedeAC495271d0F"
    dex_swap_topic_uniswap_v2: str = "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"

    smart_money_horizons: str = "1m,5m,15m,30m,1h,4h,12h,24h"
    min_smart_money_events: int = 10
    min_win_return_pct: float = 0.5

    smart_money_weight_win_rate: float = 0.20
    smart_money_weight_avg_return: float = 0.20
    smart_money_weight_profit_factor: float = 0.15
    smart_money_weight_timing: float = 0.15
    smart_money_weight_entry_quality: float = 0.10
    smart_money_weight_mfe_mae: float = 0.10
    smart_money_weight_consistency: float = 0.10

    score_poor_threshold: float = 40
    score_weak_threshold: float = 60
    score_average_threshold: float = 70
    score_good_threshold: float = 80
    score_strong_threshold: float = 90

    # Backtest (Phase 10)
    backtest_entry_rule: str = "NEXT_CANDLE_OPEN"  # NEXT_CANDLE_OPEN | NEXT_CANDLE_CLOSE | NEXT_AVAILABLE_PRICE
    backtest_horizons: str = "1m,5m,15m,30m,1h,4h,12h,24h"
    backtest_neutral_threshold_pct: float = 0.1
    backtest_random_baseline_iterations: int = 100

    def validate_signal_weights(self) -> bool:
        weights = [
            self.signal_weight_whale_consensus,
            self.signal_weight_smart_money,
            self.signal_weight_net_whale_flow,
            self.signal_weight_independent_whales,
            self.signal_weight_market_confirmation,
            self.signal_weight_liquidity,
            self.signal_weight_volume,
            self.signal_weight_entry_timing,
            self.signal_weight_market_quality,
        ]
        return abs(sum(weights) - 1.0) < 1e-6

settings = Settings()
''')

# --------------------------------------------------------------------
# 2. Update models.py: add BacktestRun and BacktestResult
# --------------------------------------------------------------------
write("src/storage/models.py", r'''
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, JSON, Index, UniqueConstraint, ForeignKey
from sqlalchemy.orm import declarative_base
from datetime import datetime, UTC

Base = declarative_base()

class Wallet(Base):
    __tablename__ = "wallets"
    id = Column(Integer, primary_key=True)
    address = Column(String, nullable=False)
    chain = Column(String, nullable=False)
    first_seen = Column(DateTime, default=lambda: datetime.now(UTC))
    last_seen = Column(DateTime, default=lambda: datetime.now(UTC))
    balance_usd = Column(Float, default=0.0)
    portfolio_value_usd = Column(Float, default=0.0)
    transaction_count = Column(Integer, default=0)
    whale_score = Column(Float, nullable=True)
    smart_money_score = Column(Float, nullable=True)
    predictive_wallet_score = Column(Float, nullable=True)
    status = Column(String, default="active")
    extra_data = Column(JSON, nullable=True)

    total_volume_usd = Column(Float, default=0.0)
    buy_volume_usd = Column(Float, default=0.0)
    sell_volume_usd = Column(Float, default=0.0)
    net_flow_usd = Column(Float, default=0.0)
    swap_count = Column(Integer, default=0)
    buy_count = Column(Integer, default=0)
    sell_count = Column(Integer, default=0)
    average_trade_size_usd = Column(Float, default=0.0)
    largest_trade_size_usd = Column(Float, default=0.0)
    unique_tokens = Column(Integer, default=0)
    unique_dexes = Column(Integer, default=0)
    active_days = Column(Integer, default=0)
    address_type = Column(String, default="unknown")
    exclusion_reason = Column(String, nullable=True)

    smart_money_status = Column(String, default="INSUFFICIENT_DATA")
    win_rate = Column(Float, nullable=True)
    average_return = Column(Float, nullable=True)
    median_return = Column(Float, nullable=True)
    profit_factor = Column(Float, nullable=True)
    timing_accuracy = Column(Float, nullable=True)
    entry_quality = Column(Float, nullable=True)
    average_mfe = Column(Float, nullable=True)
    average_mae = Column(Float, nullable=True)
    sample_size = Column(Integer, default=0)
    performance_confidence = Column(Float, nullable=True)
    performance_updated_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint('chain', 'address', name='uq_wallets_chain_address'),
        Index('ix_wallets_chain_address', 'chain', 'address'),
        Index('ix_wallets_chain_whale_score', 'chain', 'whale_score'),
        Index('ix_wallets_chain_last_seen', 'chain', 'last_seen'),
        Index('ix_wallets_chain_total_volume', 'chain', 'total_volume_usd'),
        Index('ix_wallets_chain_status', 'chain', 'status'),
    )

class WalletActivity(Base):
    __tablename__ = "wallet_activity"
    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, ForeignKey('wallets.id'), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    window = Column(String, nullable=False)
    buy_volume = Column(Float, default=0.0)
    sell_volume = Column(Float, default=0.0)
    net_flow = Column(Float, default=0.0)
    swap_count = Column(Integer, default=0)
    average_trade = Column(Float, default=0.0)
    largest_trade = Column(Float, default=0.0)

    __table_args__ = (
        Index('ix_wallet_activity_wallet_time', 'wallet_id', 'timestamp'),
        Index('ix_wallet_activity_wallet_window', 'wallet_id', 'window'),
    )

class WalletTokenActivity(Base):
    __tablename__ = "wallet_token_activity"
    id = Column(Integer, primary_key=True)
    wallet_id = Column(Integer, ForeignKey('wallets.id'), nullable=False)
    token_address = Column(String, nullable=False)
    token_symbol = Column(String, nullable=True)
    buy_volume = Column(Float, default=0.0)
    sell_volume = Column(Float, default=0.0)
    buy_count = Column(Integer, default=0)
    sell_count = Column(Integer, default=0)
    first_seen = Column(DateTime, nullable=True)
    last_seen = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint('wallet_id', 'token_address', name='uq_wallet_token'),
        Index('ix_wallet_token_wallet', 'wallet_id'),
        Index('ix_wallet_token_token', 'token_address'),
    )

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    chain = Column(String, nullable=False)
    network = Column(String, nullable=False)
    block_number = Column(Integer, nullable=False)
    block_hash = Column(String)
    transaction_hash = Column(String, nullable=False, unique=True)
    transaction_index = Column(Integer)
    from_address = Column(String)
    to_address = Column(String)
    value = Column(Float)
    timestamp = Column(DateTime, nullable=False)
    status = Column(String)
    classification = Column(String)
    confidence = Column(Float)
    log_index = Column(Integer, default=0)
    extra_data = Column(JSON, nullable=True)

    __table_args__ = (
        Index('ix_transactions_chain_timestamp', 'chain', 'timestamp'),
        Index('ix_transactions_chain_address_timestamp', 'chain', 'from_address', 'timestamp'),
        Index('ix_transactions_hash', 'transaction_hash'),
    )

class WhaleEvent(Base):
    __tablename__ = "whale_events"
    id = Column(Integer, primary_key=True)
    chain = Column(String, nullable=False)
    wallet = Column(String, nullable=False)
    token = Column(String, nullable=False)
    side = Column(String, nullable=False)
    usd_value = Column(Float)
    timestamp = Column(DateTime, nullable=False)
    transaction_hash = Column(String)
    dex = Column(String)
    whale_score = Column(Float)
    smart_money_score = Column(Float)
    predictive_wallet_score = Column(Float)
    confidence = Column(Float)
    regime = Column(String)
    extra_data = Column(JSON, nullable=True)

    __table_args__ = (
        Index('ix_whale_events_chain_token_timestamp', 'chain', 'token', 'timestamp'),
        Index('ix_whale_events_wallet_timestamp', 'wallet', 'timestamp'),
    )

class Signal(Base):
    __tablename__ = "signals"
    id = Column(Integer, primary_key=True)
    token = Column(String, nullable=False)
    chain = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    direction = Column(String, default="NEUTRAL")
    signal_score = Column(Float, default=0.0)
    confidence = Column(Float, default=0.0)
    status = Column(String, default="INSUFFICIENT_DATA")
    whale_consensus_score = Column(Float, nullable=True)
    whale_consensus_confidence = Column(Float, nullable=True)
    smart_money_score = Column(Float, nullable=True)
    net_whale_flow = Column(Float, nullable=True)
    independent_whales = Column(Integer, default=0)
    market_confirmation_score = Column(Float, nullable=True)
    entry_timing_score = Column(Float, nullable=True)
    liquidity_score = Column(Float, nullable=True)
    volume_score = Column(Float, nullable=True)
    volatility_score = Column(Float, nullable=True)
    gate_available = Column(Boolean, default=False)
    conflict_detected = Column(Boolean, default=False)
    components = Column(JSON, nullable=True)
    rejection_reasons = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index('ix_signals_chain_token_timestamp', 'chain', 'token', 'timestamp'),
    )

class WalletPerformance(Base):
    __tablename__ = "wallet_performance"
    id = Column(Integer, primary_key=True)
    wallet = Column(String, nullable=False)
    chain = Column(String, nullable=False)
    token = Column(String, nullable=False)
    tx_hash = Column(String, nullable=False)
    block_number = Column(Integer, nullable=False)
    buy_timestamp = Column(DateTime, nullable=False)
    entry_price = Column(Float, nullable=True)
    entry_usd_value = Column(Float, nullable=True)
    amount = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    dex = Column(String, nullable=True)
    regime = Column(String, nullable=True)

    return_1m = Column(Float, nullable=True)
    return_5m = Column(Float, nullable=True)
    return_15m = Column(Float, nullable=True)
    return_30m = Column(Float, nullable=True)
    return_1h = Column(Float, nullable=True)
    return_4h = Column(Float, nullable=True)
    return_12h = Column(Float, nullable=True)
    return_24h = Column(Float, nullable=True)

    mfe_5m = Column(Float, nullable=True)
    mfe_15m = Column(Float, nullable=True)
    mfe_30m = Column(Float, nullable=True)
    mfe_1h = Column(Float, nullable=True)
    mfe_4h = Column(Float, nullable=True)
    mfe_24h = Column(Float, nullable=True)

    mae_5m = Column(Float, nullable=True)
    mae_15m = Column(Float, nullable=True)
    mae_30m = Column(Float, nullable=True)
    mae_1h = Column(Float, nullable=True)
    mae_4h = Column(Float, nullable=True)
    mae_24h = Column(Float, nullable=True)

    win_1h = Column(Boolean, nullable=True)
    win_4h = Column(Boolean, nullable=True)
    win_24h = Column(Boolean, nullable=True)

    evaluation_status = Column(String, default="PENDING")

    __table_args__ = (
        UniqueConstraint('chain', 'tx_hash', name='uq_wallet_perf_chain_tx'),
        Index('ix_wallet_perf_wallet_timestamp', 'wallet', 'buy_timestamp'),
        Index('ix_wallet_perf_chain_token_timestamp', 'chain', 'token', 'buy_timestamp'),
    )

class ExcludedAddress(Base):
    __tablename__ = "excluded_addresses"
    id = Column(Integer, primary_key=True)
    address = Column(String, nullable=False)
    chain = Column(String, nullable=False)
    label = Column(String)
    reason = Column(String)
    source = Column(String)

    __table_args__ = (
        Index('ix_excluded_addresses_chain_address', 'chain', 'address'),
    )

class TokenStats(Base):
    __tablename__ = "token_stats"
    id = Column(Integer, primary_key=True)
    token = Column(String, nullable=False)
    chain = Column(String, nullable=False)
    market_cap = Column(Float, nullable=True)
    volume_24h = Column(Float, nullable=True)
    liquidity = Column(Float, nullable=True)
    price = Column(Float, nullable=True)
    gate_available = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC))

class WhaleConsensus(Base):
    __tablename__ = "whale_consensus"
    id = Column(Integer, primary_key=True)
    token = Column(String, nullable=False)
    chain = Column(String, nullable=False)
    window_start = Column(DateTime, nullable=False)
    window_end = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    total_buy_volume = Column(Float, default=0.0)
    total_sell_volume = Column(Float, default=0.0)
    net_whale_flow = Column(Float, default=0.0)

    unique_buying_wallets = Column(Integer, default=0)
    unique_selling_wallets = Column(Integer, default=0)
    independent_buying_whales = Column(Integer, default=0)
    independent_selling_whales = Column(Integer, default=0)

    buy_event_count = Column(Integer, default=0)
    sell_event_count = Column(Integer, default=0)

    average_whale_score = Column(Float, nullable=True)
    weighted_whale_score = Column(Float, nullable=True)
    average_smart_money_score = Column(Float, nullable=True)
    weighted_smart_money_score = Column(Float, nullable=True)

    temporal_convergence_score = Column(Float, default=0.0)
    whale_agreement_score = Column(Float, default=0.0)
    wallet_breadth_score = Column(Float, default=0.0)
    volume_strength_score = Column(Float, default=0.0)

    consensus_score = Column(Float, default=0.0)
    confidence = Column(Float, default=0.0)

    direction = Column(String, default="NEUTRAL")
    status = Column(String, default="INSUFFICIENT_SAMPLE")

    data_quality_score = Column(Float, default=0.0)
    components = Column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint('chain', 'token', 'window_start', name='uq_consensus_chain_token_window'),
        Index('ix_consensus_chain_token_window', 'chain', 'token', 'window_start'),
    )

class Block(Base):
    __tablename__ = "blocks"
    id = Column(Integer, primary_key=True)
    chain = Column(String, nullable=False)
    network = Column(String, nullable=False)
    block_number = Column(Integer, nullable=False)
    block_hash = Column(String, nullable=False, unique=True)
    parent_hash = Column(String)
    timestamp = Column(DateTime, nullable=False)
    transaction_count = Column(Integer, default=0)
    status = Column(String, default="pending")
    extra_data = Column(JSON, nullable=True)

    __table_args__ = (
        Index('ix_blocks_chain_number', 'chain', 'block_number'),
        Index('ix_blocks_chain_timestamp', 'chain', 'timestamp'),
    )

class TokenTransfer(Base):
    __tablename__ = "token_transfers"
    id = Column(Integer, primary_key=True)
    chain = Column(String, nullable=False)
    network = Column(String, nullable=False)
    block_number = Column(Integer, nullable=False)
    block_hash = Column(String)
    transaction_hash = Column(String, nullable=False)
    log_index = Column(Integer, nullable=False)
    token_address = Column(String, nullable=False)
    from_address = Column(String, nullable=False)
    to_address = Column(String, nullable=False)
    amount_raw = Column(String, nullable=False)
    amount_normalized = Column(Float, nullable=True)
    decimals = Column(Integer, nullable=True)
    token_symbol = Column(String, nullable=True)
    timestamp = Column(DateTime, nullable=False)
    status = Column(String, default="pending")
    extra_data = Column(JSON, nullable=True)

    __table_args__ = (
        Index('ix_token_transfers_chain_token', 'chain', 'token_address', 'timestamp'),
        Index('ix_token_transfers_chain_tx', 'chain', 'transaction_hash'),
        Index('ix_token_transfers_chain_from', 'chain', 'from_address', 'timestamp'),
        Index('ix_token_transfers_chain_to', 'chain', 'to_address', 'timestamp'),
    )

class EventLog(Base):
    __tablename__ = "event_logs"
    id = Column(Integer, primary_key=True)
    chain = Column(String, nullable=False)
    network = Column(String, nullable=False)
    block_number = Column(Integer, nullable=False)
    block_hash = Column(String)
    transaction_hash = Column(String, nullable=False)
    transaction_index = Column(Integer)
    log_index = Column(Integer, nullable=False)
    contract_address = Column(String, nullable=False)
    topic0 = Column(String, nullable=False)
    topics = Column(JSON, nullable=True)
    data = Column(JSON, nullable=True)
    timestamp = Column(DateTime, nullable=False)
    status = Column(String, default="pending")
    extra_data = Column(JSON, nullable=True)

    __table_args__ = (
        Index('ix_event_logs_chain_contract', 'chain', 'contract_address', 'timestamp'),
        Index('ix_event_logs_chain_tx', 'chain', 'transaction_hash'),
        Index('ix_event_logs_chain_timestamp', 'chain', 'timestamp'),
    )

class Swap(Base):
    __tablename__ = "swaps"
    id = Column(Integer, primary_key=True)
    chain = Column(String, nullable=False)
    dex = Column(String, nullable=False)
    protocol_version = Column(String, nullable=True)
    tx_hash = Column(String, nullable=False)
    block_number = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    log_index = Column(Integer, nullable=False)
    wallet_address = Column(String, nullable=False)
    token_in = Column(String, nullable=False)
    token_out = Column(String, nullable=False)
    amount_in_raw = Column(String, nullable=True)
    amount_out_raw = Column(String, nullable=True)
    amount_in = Column(Float, nullable=True)
    amount_out = Column(Float, nullable=True)
    token_in_decimals = Column(Integer, nullable=True)
    token_out_decimals = Column(Integer, nullable=True)
    token_in_symbol = Column(String, nullable=True)
    token_out_symbol = Column(String, nullable=True)
    side = Column(String, nullable=False)
    native_value = Column(Float, nullable=True)
    usd_value = Column(Float, nullable=True)
    pool_address = Column(String, nullable=True)
    router_address = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    classification_reason = Column(String, nullable=True)
    swap_group_id = Column(String, nullable=True)
    extra_data = Column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint('chain', 'tx_hash', 'log_index', name='uq_swap_chain_tx_log'),
        Index('ix_swaps_chain_tx', 'chain', 'tx_hash'),
        Index('ix_swaps_chain_wallet_timestamp', 'chain', 'wallet_address', 'timestamp'),
        Index('ix_swaps_chain_token_in_timestamp', 'chain', 'token_in', 'timestamp'),
        Index('ix_swaps_chain_token_out_timestamp', 'chain', 'token_out', 'timestamp'),
        Index('ix_swaps_chain_dex_timestamp', 'chain', 'dex', 'timestamp'),
        Index('ix_swaps_side_timestamp', 'side', 'timestamp'),
    )

class BacktestRun(Base):
    __tablename__ = "backtest_runs"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    config_snapshot = Column(JSON, nullable=True)
    dataset_info = Column(String, nullable=True)
    status = Column(String, default="RUNNING")

class BacktestResult(Base):
    __tablename__ = "backtest_results"
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey('backtest_runs.id'), nullable=False)
    signal_id = Column(Integer, nullable=True)
    token = Column(String, nullable=False)
    chain = Column(String, nullable=False)
    signal_timestamp = Column(DateTime, nullable=False)
    direction = Column(String, nullable=False)
    signal_score = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    entry_price = Column(Float, nullable=True)
    horizon = Column(String, nullable=False)
    future_price = Column(Float, nullable=True)
    return_pct = Column(Float, nullable=True)
    outcome = Column(String, nullable=True)  # WIN/LOSS/NEUTRAL
    mfe = Column(Float, nullable=True)
    mae = Column(Float, nullable=True)

    __table_args__ = (
        Index('ix_backtest_results_run', 'run_id'),
        Index('ix_backtest_results_chain_token_time', 'chain', 'token', 'signal_timestamp'),
    )
''')

# --------------------------------------------------------------------
# 3. Update repositories.py with backtest repos
# --------------------------------------------------------------------
write("src/storage/repositories.py", r'''
from typing import List, Optional
from sqlalchemy.orm import Session
from src.storage.models import (
    Wallet, Transaction, WhaleEvent, Signal, ExcludedAddress, TokenStats,
    WhaleConsensus, Block, TokenTransfer, EventLog, Swap,
    WalletActivity, WalletTokenActivity, BacktestRun, BacktestResult
)

class BaseRepository:
    def __init__(self, session: Session):
        self.session = session

class WalletRepository(BaseRepository):
    def get_by_address(self, chain: str, address: str) -> Optional[Wallet]:
        return self.session.query(Wallet).filter_by(chain=chain, address=address).first()
    def add(self, wallet: Wallet):
        self.session.add(wallet)

class WalletActivityRepository(BaseRepository):
    def add(self, activity: WalletActivity):
        self.session.add(activity)

class WalletTokenActivityRepository(BaseRepository):
    def add(self, activity: WalletTokenActivity):
        self.session.add(activity)

class TransactionRepository(BaseRepository):
    def get_by_hash(self, tx_hash: str) -> Optional[Transaction]:
        return self.session.query(Transaction).filter_by(transaction_hash=tx_hash).first()
    def add(self, tx: Transaction):
        self.session.add(tx)

class WhaleEventRepository(BaseRepository):
    def add(self, event: WhaleEvent):
        self.session.add(event)

class SignalRepository(BaseRepository):
    def add(self, signal: Signal):
        self.session.add(signal)
    def get_by_token_timestamp(self, chain: str, token: str, timestamp) -> Optional[Signal]:
        return self.session.query(Signal).filter_by(chain=chain, token=token, timestamp=timestamp).first()
    def get_recent_signals(self, chain: str, limit: int = 100) -> List[Signal]:
        return self.session.query(Signal).filter_by(chain=chain).order_by(Signal.timestamp.desc()).limit(limit).all()

class ExcludedAddressRepository(BaseRepository):
    def get_by_address(self, chain: str, address: str) -> Optional[ExcludedAddress]:
        return self.session.query(ExcludedAddress).filter_by(chain=chain, address=address).first()
    def add(self, excluded: ExcludedAddress):
        self.session.add(excluded)

class TokenStatsRepository(BaseRepository):
    def get_by_token(self, chain: str, token: str) -> Optional[TokenStats]:
        return self.session.query(TokenStats).filter_by(chain=chain, token=token).first()
    def add(self, stats: TokenStats):
        self.session.add(stats)

class WhaleConsensusRepository(BaseRepository):
    def add(self, consensus: WhaleConsensus):
        self.session.add(consensus)
    def get_by_window(self, chain: str, token: str, window_start) -> Optional[WhaleConsensus]:
        return self.session.query(WhaleConsensus).filter_by(chain=chain, token=token, window_start=window_start).first()
    def get_recent(self, chain: str, limit: int = 10) -> List[WhaleConsensus]:
        return self.session.query(WhaleConsensus).filter_by(chain=chain).order_by(WhaleConsensus.window_start.desc()).limit(limit).all()
    def get_token_consensus(self, chain: str, token: str) -> List[WhaleConsensus]:
        return self.session.query(WhaleConsensus).filter_by(chain=chain, token=token).order_by(WhaleConsensus.window_start.desc()).all()
    def get_bullish(self, chain: str) -> List[WhaleConsensus]:
        return self.session.query(WhaleConsensus).filter_by(chain=chain, direction="BULLISH").all()
    def get_bearish(self, chain: str) -> List[WhaleConsensus]:
        return self.session.query(WhaleConsensus).filter_by(chain=chain, direction="BEARISH").all()

class BlockRepository(BaseRepository):
    def get_by_hash(self, block_hash: str) -> Optional[Block]:
        return self.session.query(Block).filter_by(block_hash=block_hash).first()
    def get_by_number(self, chain: str, block_number: int) -> Optional[Block]:
        return self.session.query(Block).filter_by(chain=chain, block_number=block_number).first()
    def add(self, block: Block):
        self.session.add(block)

class TokenTransferRepository(BaseRepository):
    def get_by_tx_log(self, tx_hash: str, log_index: int) -> Optional[TokenTransfer]:
        return self.session.query(TokenTransfer).filter_by(transaction_hash=tx_hash, log_index=log_index).first()
    def add(self, transfer: TokenTransfer):
        self.session.add(transfer)

class EventLogRepository(BaseRepository):
    def get_by_tx_log(self, tx_hash: str, log_index: int) -> Optional[EventLog]:
        return self.session.query(EventLog).filter_by(transaction_hash=tx_hash, log_index=log_index).first()
    def add(self, log: EventLog):
        self.session.add(log)

class SwapRepository(BaseRepository):
    def get_by_tx_log(self, chain: str, tx_hash: str, log_index: int) -> Optional[Swap]:
        return self.session.query(Swap).filter_by(chain=chain, tx_hash=tx_hash, log_index=log_index).first()
    def add(self, swap: Swap):
        self.session.add(swap)
    def get_all_valid_swaps(self, chain: str) -> List[Swap]:
        return self.session.query(Swap).filter(Swap.chain == chain, Swap.side.in_(['BUY', 'SELL'])).all()

class BacktestRunRepository(BaseRepository):
    def add(self, run: BacktestRun):
        self.session.add(run)
    def get(self, run_id: int) -> Optional[BacktestRun]:
        return self.session.query(BacktestRun).filter_by(id=run_id).first()
    def list(self) -> List[BacktestRun]:
        return self.session.query(BacktestRun).order_by(BacktestRun.created_at.desc()).all()

class BacktestResultRepository(BaseRepository):
    def add(self, result: BacktestResult):
        self.session.add(result)
    def get_by_run(self, run_id: int) -> List[BacktestResult]:
        return self.session.query(BacktestResult).filter_by(run_id=run_id).all()
''')

# --------------------------------------------------------------------
# 4. Research modules
# --------------------------------------------------------------------
write("src/research/event_engine.py", r'''
from typing import List, Any, Callable
from datetime import datetime

class EventEngine:
    """Sorts events by timestamp and processes chronologically."""
    def __init__(self, events: List[Any], timestamp_getter: Callable[[Any], datetime]):
        self.events = sorted(events, key=timestamp_getter)
        self.index = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.index >= len(self.events):
            raise StopIteration
        event = self.events[self.index]
        self.index += 1
        return event

    def process(self, callback: Callable[[Any], None]):
        for event in self:
            callback(event)
''')

write("src/research/evaluator.py", r'''
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from src.core.config import settings

def parse_horizons(horizons_str: str) -> List[Tuple[str, timedelta]]:
    mapping = {
        '1m': timedelta(minutes=1),
        '5m': timedelta(minutes=5),
        '15m': timedelta(minutes=15),
        '30m': timedelta(minutes=30),
        '1h': timedelta(hours=1),
        '4h': timedelta(hours=4),
        '12h': timedelta(hours=12),
        '24h': timedelta(hours=24),
    }
    horizons = []
    for part in horizons_str.split(','):
        part = part.strip()
        if part in mapping:
            horizons.append((part, mapping[part]))
        else:
            raise ValueError(f"Unknown horizon: {part}")
    return horizons

def find_entry_price(candles: pd.DataFrame, signal_time: datetime) -> Optional[float]:
    """Deterministic entry price: first candle after signal_time open."""
    after = candles[candles['timestamp'] > signal_time]
    if after.empty:
        return None
    return after.iloc[0]['open']

def find_future_price(candles: pd.DataFrame, signal_time: datetime, horizon_delta: timedelta) -> Optional[float]:
    target_time = signal_time + horizon_delta
    future_candles = candles[candles['timestamp'] >= target_time]
    if future_candles.empty:
        return None
    return future_candles.iloc[0]['close']  # close of first candle at/after horizon

def compute_mfe_mae(candles: pd.DataFrame, entry_time: datetime, entry_price: float, horizon_delta: timedelta, direction: str) -> Tuple[Optional[float], Optional[float]]:
    """Returns MFE and MAE as percentage (positive numbers)."""
    end_time = entry_time + horizon_delta
    window = candles[(candles['timestamp'] > entry_time) & (candles['timestamp'] <= end_time)]
    if window.empty:
        return None, None
    if direction == 'LONG':
        max_high = window['high'].max()
        min_low = window['low'].min()
        mfe = (max_high - entry_price) / entry_price * 100
        mae = (entry_price - min_low) / entry_price * 100
    elif direction == 'SHORT':
        max_high = window['high'].max()
        min_low = window['low'].min()
        mfe = (entry_price - min_low) / entry_price * 100
        mae = (max_high - entry_price) / entry_price * 100
    else:
        mfe, mae = None, None
    return mfe, mae

def evaluate_signal(signal: Dict[str, Any], price_data: Dict[str, pd.DataFrame]) -> List[Dict[str, Any]]:
    """
    Evaluate a single signal for all horizons.
    signal: dict with keys: token, chain, timestamp, direction, signal_score, confidence, etc.
    price_data: dict token -> DataFrame with columns: timestamp, open, high, low, close
    Returns list of result dicts for each horizon.
    """
    token = signal['token']
    direction = signal.get('direction')
    if direction not in ['LONG', 'SHORT']:
        return []

    candles = price_data.get(token)
    if candles is None or candles.empty:
        return []

    signal_time = signal['timestamp']
    entry_price = find_entry_price(candles, signal_time)
    if entry_price is None or entry_price <= 0:
        return []

    horizons = parse_horizons(settings.backtest_horizons)
    results = []
    for horizon_name, horizon_delta in horizons:
        future_price = find_future_price(candles, signal_time, horizon_delta)
        if future_price is None:
            continue
        if direction == 'LONG':
            return_pct = (future_price - entry_price) / entry_price * 100
        else:
            return_pct = (entry_price - future_price) / entry_price * 100

        # Outcome
        threshold = settings.backtest_neutral_threshold_pct
        if return_pct > threshold:
            outcome = 'WIN'
        elif return_pct < -threshold:
            outcome = 'LOSS'
        else:
            outcome = 'NEUTRAL'

        # MFE/MAE
        entry_time = candles[candles['timestamp'] > signal_time].iloc[0]['timestamp']
        mfe, mae = compute_mfe_mae(candles, entry_time, entry_price, horizon_delta, direction)

        results.append({
            'signal': signal,
            'token': token,
            'chain': signal.get('chain', 'ethereum'),
            'signal_timestamp': signal_time,
            'direction': direction,
            'signal_score': signal.get('signal_score'),
            'confidence': signal.get('confidence'),
            'entry_price': entry_price,
            'horizon': horizon_name,
            'future_price': future_price,
            'return_pct': return_pct,
            'outcome': outcome,
            'mfe': mfe,
            'mae': mae,
        })
    return results
''')

write("src/research/backtester.py", r'''
from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
from src.research.evaluator import evaluate_signal
from src.research.event_engine import EventEngine

class Backtester:
    def __init__(self, price_data: Dict[str, pd.DataFrame], signals: List[Dict[str, Any]]):
        self.price_data = price_data
        self.signals = signals

    def run(self) -> List[Dict[str, Any]]:
        """Run backtest chronologically and return all evaluation records."""
        # Ensure signals are sorted by timestamp
        engine = EventEngine(self.signals, lambda s: s['timestamp'])
        all_results = []
        for signal in engine:
            results = evaluate_signal(signal, self.price_data)
            all_results.extend(results)
        return all_results
''')

write("src/research/metrics.py", r'''
from typing import List, Dict, Any, Optional
import numpy as np
from scipy import stats

def wilson_interval(wins: int, total: int, z: float = 1.96) -> Tuple[float, float]:
    """95% Wilson confidence interval for win rate."""
    if total == 0:
        return (0.0, 0.0)
    p = wins / total
    denominator = 1 + z**2 / total
    centre_adjusted = p + z**2 / (2 * total)
    adjusted_interval = z * np.sqrt((p * (1 - p) + z**2 / (4 * total)) / total)
    lower = (centre_adjusted - adjusted_interval) / denominator
    upper = (centre_adjusted + adjusted_interval) / denominator
    return (max(0, lower), min(1, upper))

def compute_basic_stats(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not results:
        return {
            'total_signals': 0,
            'wins': 0,
            'losses': 0,
            'neutral': 0,
            'win_rate': 0.0,
            'avg_return': 0.0,
            'median_return': 0.0,
            'profit_factor': 0.0,
            'best_return': 0.0,
            'worst_return': 0.0,
            'avg_mfe': 0.0,
            'avg_mae': 0.0,
            'sample_size': 0,
            'wilson_lower': 0.0,
            'wilson_upper': 0.0,
        }
    returns = [r['return_pct'] for r in results if r.get('return_pct') is not None]
    outcomes = [r['outcome'] for r in results if r.get('outcome')]
    wins = outcomes.count('WIN')
    losses = outcomes.count('LOSS')
    neutral = outcomes.count('NEUTRAL')
    total = len(results)
    win_rate = wins / total if total > 0 else 0.0
    avg_return = np.mean(returns) if returns else 0.0
    median_return = np.median(returns) if returns else 0.0
    gross_profit = sum(r for r in returns if r > 0)
    gross_loss = -sum(r for r in returns if r < 0)
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0.0)
    best_return = max(returns) if returns else 0.0
    worst_return = min(returns) if returns else 0.0
    mfes = [r['mfe'] for r in results if r.get('mfe') is not None]
    maes = [r['mae'] for r in results if r.get('mae') is not None]
    avg_mfe = np.mean(mfes) if mfes else 0.0
    avg_mae = np.mean(maes) if maes else 0.0
    wilson_lower, wilson_upper = wilson_interval(wins, total)
    return {
        'total_signals': total,
        'wins': wins,
        'losses': losses,
        'neutral': neutral,
        'win_rate': win_rate * 100,
        'avg_return': avg_return,
        'median_return': median_return,
        'profit_factor': profit_factor,
        'best_return': best_return,
        'worst_return': worst_return,
        'avg_mfe': avg_mfe,
        'avg_mae': avg_mae,
        'sample_size': total,
        'wilson_lower': wilson_lower * 100,
        'wilson_upper': wilson_upper * 100,
    }

def filter_by_score(results: List[Dict[str, Any]], min_score: float = None, max_score: float = None) -> List[Dict[str, Any]]:
    filtered = results
    if min_score is not None:
        filtered = [r for r in filtered if r.get('signal_score', 0) >= min_score]
    if max_score is not None:
        filtered = [r for r in filtered if r.get('signal_score', 0) <= max_score]
    return filtered

def filter_by_confidence(results: List[Dict[str, Any]], min_conf: float = None, max_conf: float = None) -> List[Dict[str, Any]]:
    filtered = results
    if min_conf is not None:
        filtered = [r for r in filtered if r.get('confidence', 0) >= min_conf]
    if max_conf is not None:
        filtered = [r for r in filtered if r.get('confidence', 0) <= max_conf]
    return filtered

def filter_by_direction(results: List[Dict[str, Any]], direction: str) -> List[Dict[str, Any]]:
    return [r for r in results if r.get('direction') == direction]

def score_bucket(score: float) -> str:
    if score < 50:
        return '0-49'
    elif score < 60:
        return '50-59'
    elif score < 70:
        return '60-69'
    elif score < 80:
        return '70-79'
    elif score < 90:
        return '80-89'
    else:
        return '90-100'

def compute_score_buckets(results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    buckets = {}
    for r in results:
        bucket = score_bucket(r.get('signal_score', 0))
        if bucket not in buckets:
            buckets[bucket] = []
        buckets[bucket].append(r)
    output = {}
    for bucket, bucket_results in buckets.items():
        stats = compute_basic_stats(bucket_results)
        output[bucket] = stats
    return output

def compute_confidence_buckets(results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    buckets = {}
    for r in results:
        bucket = score_bucket(r.get('confidence', 0))  # reuse bucket labels
        if bucket not in buckets:
            buckets[bucket] = []
        buckets[bucket].append(r)
    output = {}
    for bucket, bucket_results in buckets.items():
        stats = compute_basic_stats(bucket_results)
        output[bucket] = stats
    return output

def compute_horizon_stats(results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    horizons = {}
    for r in results:
        h = r['horizon']
        if h not in horizons:
            horizons[h] = []
        horizons[h].append(r)
    output = {}
    for h, h_results in horizons.items():
        output[h] = compute_basic_stats(h_results)
    return output

def compute_direction_stats(results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    directions = {}
    for r in results:
        d = r['direction']
        if d not in directions:
            directions[d] = []
        directions[d].append(r)
    output = {}
    for d, d_results in directions.items():
        output[d] = compute_basic_stats(d_results)
    return output
''')

write("src/research/baselines.py", r'''
from typing import List, Dict, Any
import random
from datetime import datetime
from src.research.evaluator import evaluate_signal

def random_baseline(signals: List[Dict[str, Any]], price_data: Dict[str, Any], iterations: int = 100) -> Dict[str, Any]:
    """
    For each signal timestamp, generate a random direction (LONG/SHORT) and evaluate.
    Returns average win rate and average return across iterations.
    """
    if not signals:
        return {'avg_win_rate': 0.0, 'avg_return': 0.0, 'iterations': 0}
    all_win_rates = []
    all_returns = []
    for i in range(iterations):
        fake_signals = []
        for sig in signals:
            fake_sig = dict(sig)
            fake_sig['direction'] = random.choice(['LONG', 'SHORT'])
            fake_signals.append(fake_sig)
        results = []
        for sig in fake_signals:
            results.extend(evaluate_signal(sig, price_data))
        if results:
            wins = sum(1 for r in results if r['outcome'] == 'WIN')
            total = len(results)
            win_rate = wins / total if total > 0 else 0
            avg_return = sum(r['return_pct'] for r in results) / total
            all_win_rates.append(win_rate)
            all_returns.append(avg_return)
    avg_win_rate = sum(all_win_rates) / len(all_win_rates) if all_win_rates else 0
    avg_return = sum(all_returns) / len(all_returns) if all_returns else 0
    return {
        'avg_win_rate': avg_win_rate * 100,
        'avg_return': avg_return,
        'iterations': iterations,
    }
''')

write("src/research/reports.py", r'''
from typing import Dict, Any, List
from src.research.metrics import (
    compute_basic_stats,
    compute_score_buckets,
    compute_confidence_buckets,
    compute_horizon_stats,
    compute_direction_stats,
)

def generate_report(backtest_results: List[Dict[str, Any]], baseline: Dict[str, Any] = None) -> Dict[str, Any]:
    overall = compute_basic_stats(backtest_results)
    long_stats = compute_basic_stats([r for r in backtest_results if r['direction'] == 'LONG'])
    short_stats = compute_basic_stats([r for r in backtest_results if r['direction'] == 'SHORT'])
    horizon_stats = compute_horizon_stats(backtest_results)
    score_buckets = compute_score_buckets(backtest_results)
    confidence_buckets = compute_confidence_buckets(backtest_results)

    report = {
        'overall': overall,
        'long': long_stats,
        'short': short_stats,
        'horizons': horizon_stats,
        'score_buckets': score_buckets,
        'confidence_buckets': confidence_buckets,
        'baseline': baseline,
    }
    return report

def export_to_csv(results: List[Dict[str, Any]], filename: str):
    import pandas as pd
    df = pd.DataFrame(results)
    df.to_csv(filename, index=False)
    return filename
''')

# --------------------------------------------------------------------
# 5. Tests
# --------------------------------------------------------------------
write("tests/unit/research/test_backtest_engine.py", r'''
import pytest
from datetime import datetime, timedelta, UTC
import pandas as pd
import numpy as np
from src.research.backtester import Backtester
from src.research.metrics import compute_basic_stats

def create_price_data():
    # Generate 1h candles for 48 hours
    start = datetime(2024,1,1,tzinfo=UTC)
    dates = [start + timedelta(hours=i) for i in range(49)]
    price = 100.0
    rows = []
    for ts in dates:
        open_price = price
        high = price * 1.02
        low = price * 0.98
        close = price * 1.01  # uptrend
        rows.append({'timestamp': ts, 'open': open_price, 'high': high, 'low': low, 'close': close})
        price = close
    df = pd.DataFrame(rows)
    return {'TOKEN': df}

def create_signals():
    start = datetime(2024,1,1,tzinfo=UTC)
    signals = []
    for i in range(0, 24, 2):  # every 2 hours
        ts = start + timedelta(hours=i)
        signals.append({
            'token': 'TOKEN',
            'chain': 'ethereum',
            'timestamp': ts,
            'direction': 'LONG',
            'signal_score': 80,
            'confidence': 80,
        })
    return signals

def test_backtest_runs():
    price_data = create_price_data()
    signals = create_signals()
    bt = Backtester(price_data, signals)
    results = bt.run()
    assert len(results) > 0
    stats = compute_basic_stats(results)
    assert stats['sample_size'] > 0
''')

write("tests/unit/research/test_no_lookahead.py", r'''
import pytest
from datetime import datetime, timedelta, UTC
import pandas as pd
from src.research.backtester import Backtester

def test_no_lookahead_future_candles():
    start = datetime(2024,1,1,tzinfo=UTC)
    dates = [start + timedelta(hours=i) for i in range(24)]
    price = 100.0
    rows = []
    for ts in dates:
        rows.append({'timestamp': ts, 'open': price, 'high': price*1.01, 'low': price*0.99, 'close': price*1.005})
        price = price*1.005
    df_before = pd.DataFrame(rows)
    # Add future candles after the last signal timestamp (signal at hour 10)
    last_signal_time = start + timedelta(hours=10)
    future_dates = [start + timedelta(hours=i) for i in range(24, 30)]
    future_rows = []
    for ts in future_dates:
        future_rows.append({'timestamp': ts, 'open': 200, 'high': 200, 'low': 200, 'close': 200})
    df_after = pd.concat([df_before, pd.DataFrame(future_rows)], ignore_index=True)
    df_after = df_after.sort_values('timestamp').reset_index(drop=True)
    signals = [{'token': 'TOKEN', 'chain': 'ethereum', 'timestamp': last_signal_time, 'direction': 'LONG', 'signal_score': 80, 'confidence': 80}]
    price_data_before = {'TOKEN': df_before}
    price_data_after = {'TOKEN': df_after}
    bt1 = Backtester(price_data_before, signals)
    bt2 = Backtester(price_data_after, signals)
    res1 = bt1.run()
    res2 = bt2.run()
    # Since signals are same and past data same, results should be identical
    assert len(res1) == len(res2)
    for r1, r2 in zip(res1, res2):
        assert r1['return_pct'] == r2['return_pct']
        assert r1['entry_price'] == r2['entry_price']
''')

write("tests/unit/research/test_mfe_mae.py", r'''
import pytest
from datetime import datetime, timedelta, UTC
import pandas as pd
from src.research.evaluator import compute_mfe_mae

def test_mfe_mae():
    entry_time = datetime(2024,1,1,12,0,tzinfo=UTC)
    entry_price = 100.0
    candles = pd.DataFrame([
        {'timestamp': entry_time + timedelta(hours=1), 'open': 100, 'high': 110, 'low': 95, 'close': 105},
        {'timestamp': entry_time + timedelta(hours=2), 'open': 105, 'high': 115, 'low': 100, 'close': 110},
    ])
    mfe, mae = compute_mfe_mae(candles, entry_time, entry_price, timedelta(hours=2), 'LONG')
    assert mfe == (115 - 100) / 100 * 100
    assert mae == (100 - 95) / 100 * 100
''')

write("tests/unit/research/test_baseline.py", r'''
import pytest
from datetime import datetime, timedelta, UTC
import pandas as pd
from src.research.baselines import random_baseline

def test_random_baseline():
    start = datetime(2024,1,1,tzinfo=UTC)
    dates = [start + timedelta(hours=i) for i in range(24)]
    rows = []
    for ts in dates:
        rows.append({'timestamp': ts, 'open': 100, 'high': 102, 'low': 98, 'close': 101})
    df = pd.DataFrame(rows)
    price_data = {'TOKEN': df}
    signals = [{'token': 'TOKEN', 'chain': 'ethereum', 'timestamp': start + timedelta(hours=5), 'direction': 'LONG', 'signal_score': 80, 'confidence': 80}]
    res = random_baseline(signals, price_data, iterations=10)
    assert 'avg_win_rate' in res
    assert res['iterations'] == 10
''')

# --------------------------------------------------------------------
# 6. Run tests, commit and push
# --------------------------------------------------------------------
print("running tests...")
result = subprocess.run([sys.executable, "-m", "pytest", "-q", "--disable-warnings"], cwd=ROOT)
if result.returncode != 0:
    print("tests failed")
    sys.exit(1)
print("tests passed")

subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)
subprocess.run(["git", "commit", "-m", "feat: add historical backtest engine (Phase 10)"], cwd=ROOT, check=True)
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
print("Phase 10 complete.")
