#!/usr/bin/env python3
"""
Phase 8 - Whale Consensus & Multi-Wallet Convergence
Creates consensus engine, updates models/config/repositories, writes tests, runs pytest, commits and pushes.
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
# 1. Update config.py with consensus parameters
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
# 2. Update models.py: update WhaleConsensus table
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
''')

# --------------------------------------------------------------------
# 3. Update repositories.py with consensus repository
# --------------------------------------------------------------------
write("src/storage/repositories.py", r'''
from typing import List, Optional
from sqlalchemy.orm import Session
from src.storage.models import (
    Wallet, Transaction, WhaleEvent, Signal, ExcludedAddress, TokenStats,
    WhaleConsensus, Block, TokenTransfer, EventLog, Swap,
    WalletActivity, WalletTokenActivity
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
        return self.session.query(WhaleConsensus).filter_by(
            chain=chain, token=token, window_start=window_start
        ).first()

    def get_recent(self, chain: str, limit: int = 10) -> List[WhaleConsensus]:
        return self.session.query(WhaleConsensus).filter_by(chain=chain).order_by(
            WhaleConsensus.window_start.desc()
        ).limit(limit).all()

    def get_token_consensus(self, chain: str, token: str) -> List[WhaleConsensus]:
        return self.session.query(WhaleConsensus).filter_by(chain=chain, token=token).order_by(
            WhaleConsensus.window_start.desc()
        ).all()

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
''')

# --------------------------------------------------------------------
# 4. Create consensus engine
# --------------------------------------------------------------------
write("src/consensus/consensus_engine.py", r'''
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, UTC
from collections import defaultdict
from src.core.config import settings
from src.storage.models import WhaleConsensus
import math

class ConsensusEngine:
    def __init__(self, window_minutes: int = None):
        self.window_minutes = window_minutes or settings.consensus_window_minutes

    def _window_start(self, timestamp: datetime) -> datetime:
        epoch = datetime(1970,1,1,tzinfo=UTC)
        delta = int((timestamp - epoch).total_seconds() // (self.window_minutes * 60))
        return epoch + timedelta(seconds=delta * self.window_minutes * 60)

    def _filter_excluded(self, events: List[Dict[str, Any]], excluded_registry) -> List[Dict[str, Any]]:
        if not excluded_registry:
            return events
        return [e for e in events if not excluded_registry.is_excluded(e.get('wallet', ''))]

    def _deduplicate_wallets(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        deduped = []
        for e in events:
            addr = e.get('wallet')
            if addr and addr not in seen:
                seen.add(addr)
                deduped.append(e)
        return deduped

    def compute_consensus(
        self,
        chain: str,
        token: str,
        events: List[Dict[str, Any]],
        as_of: Optional[datetime] = None,
        excluded_registry = None,
    ) -> Optional[WhaleConsensus]:
        if not events:
            return None

        if as_of is not None:
            events = [e for e in events if e['timestamp'] <= as_of]

        if not events:
            return None

        events = self._filter_excluded(events, excluded_registry)
        events = self._deduplicate_wallets(events)

        if not events:
            return None

        buys = [e for e in events if e.get('side') == 'BUY']
        sells = [e for e in events if e.get('side') == 'SELL']

        total_buy_volume = sum(e.get('usd_value', 0.0) or 0.0 for e in buys)
        total_sell_volume = sum(e.get('usd_value', 0.0) or 0.0 for e in sells)
        net_flow = total_buy_volume - total_sell_volume

        unique_buying_wallets = len(set(e.get('wallet') for e in buys if e.get('wallet')))
        unique_selling_wallets = len(set(e.get('wallet') for e in sells if e.get('wallet')))

        independent_buying_whales = unique_buying_wallets
        independent_selling_whales = unique_selling_wallets

        buy_event_count = len(buys)
        sell_event_count = len(sells)

        avg_whale_score = sum(e.get('whale_score', 0) or 0 for e in events) / len(events) if events else 0
        avg_smart_money_score = sum(e.get('smart_money_score', 0) or 0 for e in events) / len(events) if events else 0

        total_volume = total_buy_volume + total_sell_volume
        if total_volume > 0:
            weighted_whale = sum((e.get('whale_score', 0) or 0) * (e.get('usd_value', 0) or 0) for e in events) / total_volume
            weighted_smart = sum((e.get('smart_money_score', 0) or 0) * (e.get('usd_value', 0) or 0) for e in events) / total_volume
        else:
            weighted_whale = avg_whale_score
            weighted_smart = avg_smart_money_score

        timestamps = [e['timestamp'] for e in events]
        time_span_seconds = (max(timestamps) - min(timestamps)).total_seconds()
        window_seconds = self.window_minutes * 60
        temporal_convergence = max(0.0, 1.0 - (time_span_seconds / window_seconds)) * 100 if window_seconds > 0 else 100.0

        total_events = buy_event_count + sell_event_count
        if total_events > 0:
            agreement_raw = (buy_event_count - sell_event_count) / total_events
            whale_agreement = ((agreement_raw + 1) / 2) * 100
        else:
            whale_agreement = 50.0

        if total_sell_volume > 0:
            buy_sell_ratio = total_buy_volume / total_sell_volume
            if buy_sell_ratio >= 1:
                volume_strength = min(100.0, 50.0 + math.log10(buy_sell_ratio) * 50)
            else:
                volume_strength = max(0.0, 50.0 - math.log10(1/buy_sell_ratio) * 50)
        else:
            volume_strength = 100.0 if total_buy_volume > 0 else 0.0

        breadth_buy = min(100.0, (independent_buying_whales / settings.min_independent_whales) * 100) if settings.min_independent_whales > 0 else 100.0
        breadth_sell = min(100.0, (independent_selling_whales / settings.min_independent_whales) * 100) if settings.min_independent_whales > 0 else 100.0
        wallet_breadth = max(breadth_buy, breadth_sell) if independent_buying_whales > 0 else 0.0

        confidences = [e.get('confidence', 0) or 0 for e in events]
        data_quality_score = sum(confidences) / len(confidences) if confidences else 0.0

        score = (
            settings.consensus_weight_independent_count * min(100.0, independent_buying_whales * 20) +
            settings.consensus_weight_net_flow * min(100.0, (net_flow / settings.min_net_flow_usd) * 100) +
            settings.consensus_weight_buy_sell_ratio * min(100.0, volume_strength) +
            settings.consensus_weight_avg_whale_score * avg_whale_score +
            settings.consensus_weight_avg_smart_money_score * avg_smart_money_score +
            settings.consensus_weight_temporal_convergence * temporal_convergence +
            settings.consensus_weight_whale_agreement * whale_agreement
        )
        score = max(0.0, min(100.0, score))

        if net_flow > 0 and independent_buying_whales >= settings.min_independent_whales:
            direction = "BULLISH"
        elif net_flow < 0 and independent_selling_whales >= settings.min_independent_whales:
            direction = "BEARISH"
        else:
            direction = "NEUTRAL"

        sample_factor = min(1.0, (independent_buying_whales + independent_selling_whales) / (2 * settings.min_independent_whales))
        confidence = min(100.0, (data_quality_score * 0.5 + sample_factor * 50) * (whale_agreement / 100))

        if independent_buying_whales < settings.min_independent_whales and independent_selling_whales < settings.min_independent_whales:
            status = "INSUFFICIENT_SAMPLE"
        elif confidence < settings.min_consensus_confidence or score < settings.min_consensus_score:
            status = "WEAK"
        else:
            status = "VALID"

        window_start = self._window_start(min(timestamps))
        window_end = window_start + timedelta(minutes=self.window_minutes)

        consensus = WhaleConsensus(
            token=token,
            chain=chain,
            window_start=window_start,
            window_end=window_end,
            total_buy_volume=total_buy_volume,
            total_sell_volume=total_sell_volume,
            net_whale_flow=net_flow,
            unique_buying_wallets=unique_buying_wallets,
            unique_selling_wallets=unique_selling_wallets,
            independent_buying_whales=independent_buying_whales,
            independent_selling_whales=independent_selling_whales,
            buy_event_count=buy_event_count,
            sell_event_count=sell_event_count,
            average_whale_score=avg_whale_score,
            weighted_whale_score=weighted_whale,
            average_smart_money_score=avg_smart_money_score,
            weighted_smart_money_score=weighted_smart,
            temporal_convergence_score=temporal_convergence,
            whale_agreement_score=whale_agreement,
            wallet_breadth_score=wallet_breadth,
            volume_strength_score=volume_strength,
            consensus_score=score,
            confidence=confidence,
            direction=direction,
            status=status,
            data_quality_score=data_quality_score,
            components={
                "weights": {
                    "independent_count": settings.consensus_weight_independent_count,
                    "net_flow": settings.consensus_weight_net_flow,
                    "buy_sell_ratio": settings.consensus_weight_buy_sell_ratio,
                    "avg_whale_score": settings.consensus_weight_avg_whale_score,
                    "avg_smart_money_score": settings.consensus_weight_avg_smart_money_score,
                    "temporal_convergence": settings.consensus_weight_temporal_convergence,
                    "whale_agreement": settings.consensus_weight_whale_agreement,
                },
                "total_volume": total_buy_volume + total_sell_volume,
                "time_span_seconds": time_span_seconds,
            }
        )
        return consensus
''')

# --------------------------------------------------------------------
# 5. Create tests for consensus
# --------------------------------------------------------------------
write("tests/unit/consensus/test_consensus_basic.py", r'''
import pytest
from datetime import datetime, timedelta, UTC
from src.consensus.consensus_engine import ConsensusEngine

def make_event(wallet, side, usd_value, timestamp, whale_score=80, smart_money_score=80, confidence=90):
    return {
        "wallet": wallet,
        "side": side,
        "usd_value": usd_value,
        "timestamp": timestamp,
        "whale_score": whale_score,
        "smart_money_score": smart_money_score,
        "confidence": confidence,
    }

def test_consensus_basic():
    engine = ConsensusEngine(window_minutes=60)
    now = datetime(2024,1,1,12,0,tzinfo=UTC)
    events = [
        make_event("0x1", "BUY", 100000, now),
        make_event("0x2", "BUY", 150000, now + timedelta(minutes=5)),
        make_event("0x3", "BUY", 200000, now + timedelta(minutes=10)),
    ]
    consensus = engine.compute_consensus("ethereum", "0xtoken", events)
    assert consensus is not None
    assert consensus.direction == "BULLISH"
    assert consensus.independent_buying_whales == 3
    assert consensus.net_whale_flow > 0
    assert 0 <= consensus.consensus_score <= 100
''')

write("tests/unit/consensus/test_consensus_no_lookahead.py", r'''
import pytest
from datetime import datetime, timedelta, UTC
from src.consensus.consensus_engine import ConsensusEngine

def test_no_lookahead():
    engine = ConsensusEngine(window_minutes=60)
    now = datetime(2024,1,1,12,0,tzinfo=UTC)
    event_past = {
        "wallet": "0x1", "side": "BUY", "usd_value": 100000,
        "timestamp": now, "whale_score": 80, "smart_money_score": 80, "confidence": 90,
    }
    event_future = {
        "wallet": "0x2", "side": "BUY", "usd_value": 200000,
        "timestamp": now + timedelta(minutes=30), "whale_score": 80, "smart_money_score": 80, "confidence": 90,
    }
    as_of = now + timedelta(minutes=10)
    consensus = engine.compute_consensus("ethereum", "0xtoken", [event_past, event_future], as_of=as_of)
    assert consensus is not None
    assert consensus.independent_buying_whales == 1
    assert consensus.total_buy_volume == 100000
''')

write("tests/unit/consensus/test_consensus_duplicate.py", r'''
import pytest
from datetime import datetime, timedelta, UTC
from src.consensus.consensus_engine import ConsensusEngine

def test_duplicate_wallet_dedup():
    engine = ConsensusEngine(window_minutes=60)
    now = datetime(2024,1,1,12,0,tzinfo=UTC)
    events = [
        {"wallet": "0x1", "side": "BUY", "usd_value": 100000, "timestamp": now, "whale_score": 80, "smart_money_score": 80, "confidence": 90},
        {"wallet": "0x1", "side": "BUY", "usd_value": 50000, "timestamp": now + timedelta(minutes=1), "whale_score": 80, "smart_money_score": 80, "confidence": 90},
    ]
    consensus = engine.compute_consensus("ethereum", "0xtoken", events)
    assert consensus.independent_buying_whales == 1
''')

write("tests/unit/consensus/test_consensus_min_sample.py", r'''
import pytest
from datetime import datetime, timedelta, UTC
from src.consensus.consensus_engine import ConsensusEngine
from src.core.config import settings

def test_insufficient_sample():
    engine = ConsensusEngine(window_minutes=60)
    now = datetime(2024,1,1,12,0,tzinfo=UTC)
    events = [
        {"wallet": "0x1", "side": "BUY", "usd_value": 100000, "timestamp": now, "whale_score": 80, "smart_money_score": 80, "confidence": 90},
        {"wallet": "0x2", "side": "BUY", "usd_value": 150000, "timestamp": now + timedelta(minutes=5), "whale_score": 80, "smart_money_score": 80, "confidence": 90},
    ]
    original = settings.min_independent_whales
    settings.min_independent_whales = 3
    consensus = engine.compute_consensus("ethereum", "0xtoken", events)
    settings.min_independent_whales = original
    assert consensus.status == "INSUFFICIENT_SAMPLE"
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
subprocess.run(["git", "commit", "-m", "feat: add whale consensus engine (Phase 8)"], cwd=ROOT, check=True)
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
print("Phase 8 complete.")
