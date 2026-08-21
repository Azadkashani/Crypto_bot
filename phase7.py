#!/usr/bin/env python3
"""
Phase 7 - Smart Money Analysis
Creates all necessary modules, updates models/config, writes tests, runs pytest, commits and pushes.
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
# 1. Update config.py with Smart Money parameters
# --------------------------------------------------------------------
write("src/core/config.py", r'''
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
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

    # Consensus (not used yet)
    consensus_window_minutes: int = 60
    min_independent_whales: int = 3
    min_net_flow_usd: float = 500_000

    # Signal (not used yet)
    signal_min_score: float = 85
    signal_min_confidence: float = 80

    # Finality
    required_confirmations: int = 6

    # Rate Limit & Cost Tracking
    rate_limit_enabled: bool = True
    cost_tracking_enabled: bool = True

    # Gate.io (not used yet)
    gate_api_key: Optional[str] = None
    gate_api_secret: Optional[str] = None

    # DEX / Swap Classification (Phase 5)
    buy_confidence_threshold: float = 80
    sell_confidence_threshold: float = 80
    native_asset_symbol: str = "ETH"
    wrapped_native_symbol: str = "WETH"
    wrapped_native_address: str = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
    stablecoin_addresses_ethereum: str = "0xdAC17F958D2ee523a2206206994597C13D831ec7,0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48,0x6B175474E89094C44Da98b954EedeAC495271d0F"
    dex_swap_topic_uniswap_v2: str = "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"

    # Smart Money Analysis (Phase 7)
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

settings = Settings()
''')

# --------------------------------------------------------------------
# 2. Update models.py: add new fields to Wallet, update WalletPerformance
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

    # Whale Detection fields (Phase 6)
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

    # Smart Money summary fields (Phase 7)
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
    signal_score = Column(Float)
    confidence = Column(Float)
    components = Column(JSON)
    mode = Column(String)
    gate_available = Column(Boolean)
    regime = Column(String)
    status = Column(String)

    __table_args__ = (
        Index('ix_signals_chain_token_timestamp', 'chain', 'token', 'timestamp'),
    )

class WalletPerformance(Base):
    """Store per-trade performance evaluation results."""
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

    # Returns (percentage) for horizons
    return_1m = Column(Float, nullable=True)
    return_5m = Column(Float, nullable=True)
    return_15m = Column(Float, nullable=True)
    return_30m = Column(Float, nullable=True)
    return_1h = Column(Float, nullable=True)
    return_4h = Column(Float, nullable=True)
    return_12h = Column(Float, nullable=True)
    return_24h = Column(Float, nullable=True)

    # MFE / MAE (percentage) for some horizons
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

    # Win flags (using min_win_return_pct threshold)
    win_1h = Column(Boolean, nullable=True)
    win_4h = Column(Boolean, nullable=True)
    win_24h = Column(Boolean, nullable=True)

    evaluation_status = Column(String, default="PENDING")  # COMPLETED, PARTIAL, UNAVAILABLE, INSUFFICIENT

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
    total_buy_volume = Column(Float, default=0.0)
    total_sell_volume = Column(Float, default=0.0)
    net_flow = Column(Float, default=0.0)
    independent_whales = Column(Integer, default=0)
    consensus_score = Column(Float, default=0.0)

    __table_args__ = (
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
''')

# --------------------------------------------------------------------
# 3. Create smart_money modules
# --------------------------------------------------------------------
write("src/smart_money/__init__.py", "")

write("src/smart_money/price_provider.py", r'''
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Optional

class PriceProvider(ABC):
    @abstractmethod
    def get_price(self, token: str, timestamp: int) -> Optional[float]:
        """Return price at or before timestamp."""
        ...

class MockPriceProvider(PriceProvider):
    """Mock provider that reads from a dict of token -> list of (timestamp, price)."""
    def __init__(self, price_data: Dict[str, List[Tuple[int, float]]]):
        self.price_data = price_data

    def get_price(self, token: str, timestamp: int) -> Optional[float]:
        if token not in self.price_data:
            return None
        series = self.price_data[token]
        # Find the latest price at or before timestamp
        best = None
        for ts, price in series:
            if ts <= timestamp:
                best = price
            else:
                break
        return best
''')

write("src/smart_money/performance_evaluator.py", r'''
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from src.smart_money.price_provider import PriceProvider

@dataclass
class BuyEvent:
    wallet: str
    chain: str
    token: str
    tx_hash: str
    block_number: int
    timestamp: datetime
    entry_price: Optional[float]
    entry_usd_value: Optional[float]
    amount: Optional[float]
    confidence: float
    dex: Optional[str] = None

@dataclass
class TradeEvaluation:
    event: BuyEvent
    evaluation_status: str = "PENDING"  # COMPLETED, PARTIAL, UNAVAILABLE, INSUFFICIENT
    returns: Dict[str, Optional[float]] = field(default_factory=dict)  # horizon -> return %
    mfe: Dict[str, Optional[float]] = field(default_factory=dict)
    mae: Dict[str, Optional[float]] = field(default_factory=dict)
    win_flags: Dict[str, Optional[bool]] = field(default_factory=dict)

def calculate_return(entry_price: float, future_price: float) -> float:
    if entry_price == 0:
        return 0.0
    return (future_price - entry_price) / entry_price * 100.0

def evaluate_buy_event(
    event: BuyEvent,
    price_provider: PriceProvider,
    horizons: List[Tuple[str, timedelta]],
    min_win_return_pct: float = 0.5,
    as_of: Optional[datetime] = None
) -> TradeEvaluation:
    """
    Evaluate a buy event using price data.
    as_of: If provided, only use price data up to this time (for no look-ahead).
           The event timestamp must be <= as_of.
    """
    if as_of is not None and event.timestamp > as_of:
        return TradeEvaluation(event=event, evaluation_status="UNAVAILABLE", reason="FUTURE_EVENT")

    if event.entry_price is None or event.entry_price <= 0:
        return TradeEvaluation(event=event, evaluation_status="UNAVAILABLE", reason="NO_ENTRY_PRICE")

    evaluation = TradeEvaluation(event=event, evaluation_status="PARTIAL")

    for horizon_name, horizon_delta in horizons:
        target_time = event.timestamp + horizon_delta
        # If as_of provided and target_time > as_of, we cannot evaluate this horizon yet.
        if as_of is not None and target_time > as_of:
            evaluation.returns[horizon_name] = None
            evaluation.mfe[horizon_name] = None
            evaluation.mae[horizon_name] = None
            evaluation.win_flags[horizon_name] = None
            continue

        future_price = price_provider.get_price(event.token, int(target_time.timestamp()))
        if future_price is None:
            evaluation.returns[horizon_name] = None
            evaluation.mfe[horizon_name] = None
            evaluation.mae[horizon_name] = None
            evaluation.win_flags[horizon_name] = None
            continue

        ret = calculate_return(event.entry_price, future_price)
        evaluation.returns[horizon_name] = ret
        evaluation.win_flags[horizon_name] = ret > min_win_return_pct

        # For MFE/MAE, we need high/low between entry and target_time.
        # For simplicity, we'll use the final price as both high and low if only one price point.
        # In a real implementation, we'd need a series. Here we assume price_provider can give us the latest price only.
        # So for MFE/MAE, we approximate with the final price.
        # We'll set MFE = ret if positive else 0, MAE = -ret if negative else 0.
        if ret > 0:
            evaluation.mfe[horizon_name] = ret
            evaluation.mae[horizon_name] = 0.0
        else:
            evaluation.mfe[horizon_name] = 0.0
            evaluation.mae[horizon_name] = -ret

    # Determine evaluation status
    if all(v is None for v in evaluation.returns.values()):
        evaluation.evaluation_status = "UNAVAILABLE"
    else:
        # If all horizons have data, COMPLETED, else PARTIAL
        if all(v is not None for v in evaluation.returns.values()):
            evaluation.evaluation_status = "COMPLETED"
        else:
            evaluation.evaluation_status = "PARTIAL"
    return evaluation
''')

write("src/smart_money/smart_money_scorer.py", r'''
from typing import Dict, Any, List, Optional
from src.core.config import settings
import math

def compute_smart_money_score(
    win_rate: Optional[float],
    avg_return: Optional[float],
    profit_factor: Optional[float],
    timing_accuracy: Optional[float],
    entry_quality: Optional[float],
    mfe_mae_score: Optional[float],
    consistency_score: Optional[float],
    sample_size: int,
    min_events: int = None
) -> Dict[str, Any]:
    """
    Compute Smart Money Score (0-100) with confidence adjustment.
    All inputs are 0-100 scales except win_rate, avg_return, profit_factor which are normalized later.
    """
    if min_events is None:
        min_events = settings.min_smart_money_events

    # Convert raw metrics to scores (0-100) if not already.
    # win_rate expected as percentage 0-100 already.
    # avg_return expected as percentage.
    # profit_factor is ratio; convert to 0-100 using log scale or cap.
    def profit_factor_score(pf: Optional[float]) -> float:
        if pf is None:
            return 0.0
        if pf <= 0:
            return 0.0
        if pf == float('inf'):
            return 100.0
        # log scale between 0.5 and 3.0 -> 0-100
        log_pf = math.log(pf)
        log_min = math.log(0.5)
        log_max = math.log(3.0)
        normalized = (log_pf - log_min) / (log_max - log_min)
        return max(0.0, min(100.0, normalized * 100.0))

    # Consistency score: maybe derived from variance of returns; for simplicity, we'll accept direct.
    # For now, all metrics must be normalized to 0-100.

    weights = {
        'win_rate': settings.smart_money_weight_win_rate,
        'avg_return': settings.smart_money_weight_avg_return,
        'profit_factor': settings.smart_money_weight_profit_factor,
        'timing': settings.smart_money_weight_timing,
        'entry_quality': settings.smart_money_weight_entry_quality,
        'mfe_mae': settings.smart_money_weight_mfe_mae,
        'consistency': settings.smart_money_weight_consistency,
    }

    # Prepare scores; if missing, use 0.
    win_score = win_rate if win_rate is not None else 0.0
    avg_return_score = avg_return if avg_return is not None else 0.0
    pf_score = profit_factor_score(profit_factor) if profit_factor is not None else 0.0
    timing_score = timing_accuracy if timing_accuracy is not None else 0.0
    entry_quality_score = entry_quality if entry_quality is not None else 0.0
    mfe_mae_score = mfe_mae_score if mfe_mae_score is not None else 0.0
    consistency_score = consistency_score if consistency_score is not None else 0.0

    raw_score = (
        weights['win_rate'] * win_score +
        weights['avg_return'] * avg_return_score +
        weights['profit_factor'] * pf_score +
        weights['timing'] * timing_score +
        weights['entry_quality'] * entry_quality_score +
        weights['mfe_mae'] * mfe_mae_score +
        weights['consistency'] * consistency_score
    )

    # Confidence adjustment based on sample size
    if sample_size < min_events:
        # Scale down score proportionally to sample size / min_events, but not below 0.
        confidence_factor = sample_size / min_events
        final_score = raw_score * confidence_factor
        performance_confidence = confidence_factor * 100
        status = "INSUFFICIENT_DATA"
    else:
        # Full confidence, maybe slightly adjust based on sqrt(sample_size/min_events) but capped at 1.
        confidence_factor = min(1.0, math.sqrt(sample_size / min_events))
        final_score = raw_score * confidence_factor
        performance_confidence = confidence_factor * 100

    # Determine status based on final_score thresholds
    if final_score < settings.score_poor_threshold:
        status = "POOR"
    elif final_score < settings.score_weak_threshold:
        status = "WEAK"
    elif final_score < settings.score_average_threshold:
        status = "AVERAGE"
    elif final_score < settings.score_good_threshold:
        status = "GOOD"
    elif final_score < settings.score_strong_threshold:
        status = "STRONG"
    else:
        status = "EXCEPTIONAL"

    return {
        'score': max(0.0, min(100.0, final_score)),
        'status': status,
        'confidence': max(0.0, min(100.0, performance_confidence)),
        'raw_score': raw_score,
        'sample_size': sample_size,
    }
''')

write("src/smart_money/wallet_performance.py", r'''
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from src.smart_money.performance_evaluator import BuyEvent, evaluate_buy_event
from src.smart_money.smart_money_scorer import compute_smart_money_score
from src.smart_money.price_provider import PriceProvider
from src.core.config import settings
import math

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

class WalletPerformanceCalculator:
    def __init__(self, price_provider: PriceProvider, as_of: Optional[datetime] = None):
        self.price_provider = price_provider
        self.as_of = as_of
        self.horizons = parse_horizons(settings.smart_money_horizons)

    def _filter_buy_events(self, events: List[BuyEvent]) -> List[BuyEvent]:
        if self.as_of is None:
            return events
        return [e for e in events if e.timestamp <= self.as_of]

    def evaluate_events(self, events: List[BuyEvent]) -> Dict[str, Any]:
        filtered = self._filter_buy_events(events)
        evaluations = []
        for event in filtered:
            ev = evaluate_buy_event(event, self.price_provider, self.horizons,
                                    min_win_return_pct=settings.min_win_return_pct,
                                    as_of=self.as_of)
            evaluations.append(ev)
        return evaluations

    def compute_wallet_summary(self, wallet: str, events: List[BuyEvent]) -> Dict[str, Any]:
        evaluations = self.evaluate_events(events)
        valid_evals = [e for e in evaluations if e.evaluation_status in ['COMPLETED', 'PARTIAL']]
        if not valid_evals:
            return {
                'wallet': wallet,
                'sample_size': 0,
                'evaluated_events': 0,
                'win_rate': None,
                'average_return': None,
                'median_return': None,
                'profit_factor': None,
                'timing_accuracy': None,
                'entry_quality': None,
                'average_mfe': None,
                'average_mae': None,
                'consistency_score': None,
                'smart_money_score': 0.0,
                'smart_money_status': 'INSUFFICIENT_DATA',
                'performance_confidence': 0.0,
            }

        # Extract metrics per evaluation for each horizon
        win_rates = []
        returns = []
        for horizon_name, _ in self.horizons:
            horizon_returns = [e.returns.get(horizon_name) for e in valid_evals if e.returns.get(horizon_name) is not None]
            horizon_wins = [e.win_flags.get(horizon_name) for e in valid_evals if e.win_flags.get(horizon_name) is not None]
            if horizon_returns:
                returns.extend(horizon_returns)
            if horizon_wins:
                win_rate_horizon = sum(horizon_wins) / len(horizon_wins) * 100
                win_rates.append(win_rate_horizon)

        if not returns:
            return {
                'wallet': wallet,
                'sample_size': 0,
                'evaluated_events': 0,
                'win_rate': None,
                'average_return': None,
                'median_return': None,
                'profit_factor': None,
                'timing_accuracy': None,
                'entry_quality': None,
                'average_mfe': None,
                'average_mae': None,
                'consistency_score': None,
                'smart_money_score': 0.0,
                'smart_money_status': 'INSUFFICIENT_DATA',
                'performance_confidence': 0.0,
            }

        avg_win_rate = sum(win_rates) / len(win_rates) if win_rates else 0.0
        avg_return = sum(returns) / len(returns) if returns else 0.0
        median_return = sorted(returns)[len(returns)//2] if returns else 0.0

        # Profit factor: gross profit / gross loss across all horizons
        gross_profit = sum(r for r in returns if r > 0)
        gross_loss = sum(-r for r in returns if r < 0)
        if gross_loss == 0:
            profit_factor = float('inf') if gross_profit > 0 else 0.0
        else:
            profit_factor = gross_profit / gross_loss

        # MFE/MAE averages
        mfes = []
        maes = []
        for e in valid_evals:
            for horizon_name, _ in self.horizons:
                mfe_val = e.mfe.get(horizon_name)
                mae_val = e.mae.get(horizon_name)
                if mfe_val is not None:
                    mfes.append(mfe_val)
                if mae_val is not None:
                    maes.append(mae_val)

        avg_mfe = sum(mfes) / len(mfes) if mfes else 0.0
        avg_mae = sum(maes) / len(maes) if maes else 0.0

        # Timing accuracy: simplification: percentage of events with positive return at earliest horizon (e.g., 1h)
        # We'll use win rate at 1h if available, else average win rate.
        # Entry quality: simplified as avg return at 5m? We'll use avg return for all horizons.
        timing_accuracy = avg_win_rate
        entry_quality = avg_return

        # Consistency: 100 - stddev of returns (simplified)
        if len(returns) > 1:
            mean = sum(returns)/len(returns)
            variance = sum((r - mean)**2 for r in returns) / (len(returns)-1)
            stddev = math.sqrt(variance)
            consistency_score = max(0.0, 100.0 - stddev)
        else:
            consistency_score = 0.0

        # MFE/MAE ratio score: (avg_mfe / (avg_mfe + avg_mae)) * 100 if both >0
        if avg_mfe + avg_mae > 0:
            mfe_mae_score = (avg_mfe / (avg_mfe + avg_mae)) * 100
        else:
            mfe_mae_score = 50.0

        # Compute Smart Money Score using compute_smart_money_score
        smart_result = compute_smart_money_score(
            win_rate=avg_win_rate,
            avg_return=avg_return,
            profit_factor=profit_factor,
            timing_accuracy=timing_accuracy,
            entry_quality=entry_quality,
            mfe_mae_score=mfe_mae_score,
            consistency_score=consistency_score,
            sample_size=len(valid_evals),
            min_events=settings.min_smart_money_events
        )

        return {
            'wallet': wallet,
            'sample_size': len(valid_evals),
            'evaluated_events': len(valid_evals),
            'win_rate': avg_win_rate,
            'average_return': avg_return,
            'median_return': median_return,
            'profit_factor': profit_factor,
            'timing_accuracy': timing_accuracy,
            'entry_quality': entry_quality,
            'average_mfe': avg_mfe,
            'average_mae': avg_mae,
            'consistency_score': consistency_score,
            'smart_money_score': smart_result['score'],
            'smart_money_status': smart_result['status'],
            'performance_confidence': smart_result['confidence'],
        }
''')

# --------------------------------------------------------------------
# 4. Tests for Phase 7
# --------------------------------------------------------------------
write("tests/unit/smart_money/test_entry_price.py", r'''
from src.smart_money.performance_evaluator import BuyEvent, evaluate_buy_event
from src.smart_money.price_provider import MockPriceProvider
from datetime import datetime, timedelta, UTC

def test_entry_price_missing():
    provider = MockPriceProvider({})
    event = BuyEvent(wallet="0xw", chain="ethereum", token="TOKEN", tx_hash="0x1",
                     block_number=1, timestamp=datetime(2024,1,1,tzinfo=UTC),
                     entry_price=None, entry_usd_value=None, amount=None, confidence=90)
    ev = evaluate_buy_event(event, provider, [], as_of=datetime(2024,1,2,tzinfo=UTC))
    assert ev.evaluation_status == "UNAVAILABLE"
''')

write("tests/unit/smart_money/test_future_returns.py", r'''
from src.smart_money.performance_evaluator import BuyEvent, evaluate_buy_event
from src.smart_money.price_provider import MockPriceProvider
from datetime import datetime, timedelta, UTC

def test_return_1h():
    provider = MockPriceProvider({
        "TOKEN": [
            (int(datetime(2024,1,1,12,0,tzinfo=UTC).timestamp()), 100.0),
            (int(datetime(2024,1,1,13,0,tzinfo=UTC).timestamp()), 110.0),
        ]
    })
    event = BuyEvent(wallet="0xw", chain="ethereum", token="TOKEN", tx_hash="0x1",
                     block_number=1, timestamp=datetime(2024,1,1,12,0,tzinfo=UTC),
                     entry_price=100.0, entry_usd_value=None, amount=None, confidence=90)
    horizons = [("1h", timedelta(hours=1))]
    ev = evaluate_buy_event(event, provider, horizons, as_of=datetime(2024,1,1,13,0,tzinfo=UTC))
    assert ev.returns["1h"] == 10.0
    assert ev.win_flags["1h"] == True
''')

write("tests/unit/smart_money/test_no_lookahead.py", r'''
from src.smart_money.performance_evaluator import BuyEvent, evaluate_buy_event
from src.smart_money.price_provider import MockPriceProvider
from datetime import datetime, timedelta, UTC

def test_future_price_not_used_before_asof():
    provider = MockPriceProvider({
        "TOKEN": [
            (int(datetime(2024,1,1,12,0,tzinfo=UTC).timestamp()), 100.0),
            (int(datetime(2024,1,1,13,0,tzinfo=UTC).timestamp()), 110.0),
        ]
    })
    event = BuyEvent(wallet="0xw", chain="ethereum", token="TOKEN", tx_hash="0x1",
                     block_number=1, timestamp=datetime(2024,1,1,12,0,tzinfo=UTC),
                     entry_price=100.0, entry_usd_value=None, amount=None, confidence=90)
    horizons = [("1h", timedelta(hours=1))]
    # as_of = 12:30, so 1h target 13:00 > as_of => cannot evaluate
    ev = evaluate_buy_event(event, provider, horizons, as_of=datetime(2024,1,1,12,30,tzinfo=UTC))
    assert ev.returns["1h"] is None
    assert ev.win_flags["1h"] is None
''')

write("tests/unit/smart_money/test_smart_money_score.py", r'''
from src.smart_money.smart_money_scorer import compute_smart_money_score

def test_insufficient_data():
    res = compute_smart_money_score(win_rate=90, avg_return=10, profit_factor=2.0,
                                    timing_accuracy=80, entry_quality=70, mfe_mae_score=60,
                                    consistency_score=50, sample_size=5, min_events=10)
    assert res['status'] == 'INSUFFICIENT_DATA'
    assert res['score'] < res['raw_score']  # confidence adjusted

def test_full_score():
    res = compute_smart_money_score(win_rate=90, avg_return=10, profit_factor=2.0,
                                    timing_accuracy=80, entry_quality=70, mfe_mae_score=60,
                                    consistency_score=50, sample_size=20, min_events=10)
    assert res['score'] > 0
    assert res['status'] in ['GOOD', 'STRONG', 'EXCEPTIONAL']
''')

write("tests/unit/smart_money/test_wallet_summary.py", r'''
from src.smart_money.wallet_performance import WalletPerformanceCalculator
from src.smart_money.price_provider import MockPriceProvider
from src.smart_money.performance_evaluator import BuyEvent
from datetime import datetime, timedelta, UTC

def test_wallet_summary_basic():
    provider = MockPriceProvider({
        "TOKEN": [
            (int(datetime(2024,1,1,12,0,tzinfo=UTC).timestamp()), 100.0),
            (int(datetime(2024,1,1,13,0,tzinfo=UTC).timestamp()), 110.0),
            (int(datetime(2024,1,1,14,0,tzinfo=UTC).timestamp()), 108.0),
        ]
    })
    events = [
        BuyEvent(wallet="0xw", chain="ethereum", token="TOKEN", tx_hash="0x1",
                 block_number=1, timestamp=datetime(2024,1,1,12,0,tzinfo=UTC),
                 entry_price=100.0, entry_usd_value=None, amount=None, confidence=90),
        BuyEvent(wallet="0xw", chain="ethereum", token="TOKEN", tx_hash="0x2",
                 block_number=2, timestamp=datetime(2024,1,1,13,0,tzinfo=UTC),
                 entry_price=110.0, entry_usd_value=None, amount=None, confidence=90),
    ]
    calc = WalletPerformanceCalculator(provider)
    summary = calc.compute_wallet_summary("0xw", events)
    assert summary['sample_size'] == 2
    assert summary['evaluated_events'] == 2
    # Because horizons are up to 24h, as_of is None, but price data only up to 14:00, some horizons will be None.
    # But we still get some returns for 1h, 2h? Our horizons include 5m,15m,30m,1h,4h... data missing for >14h so partial.
    assert summary['smart_money_status'] in ['INSUFFICIENT_DATA', 'POOR', 'WEAK', 'AVERAGE', 'GOOD', 'STRONG', 'EXCEPTIONAL']
''')

# --------------------------------------------------------------------
# 5. Run tests, commit and push
# --------------------------------------------------------------------
print("running tests...")
result = subprocess.run([sys.executable, "-m", "pytest", "-q", "--disable-warnings"], cwd=ROOT)
if result.returncode != 0:
    print("tests failed")
    sys.exit(1)
print("tests passed")

subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)
subprocess.run(["git", "commit", "-m", "feat: add smart money analysis (Phase 7)"], cwd=ROOT, check=True)
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
print("Phase 7 complete.")
