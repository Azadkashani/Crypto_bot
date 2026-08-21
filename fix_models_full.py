#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent

def write(rel, content):
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"written: {rel}")

# محتوای کامل models.py شامل تمام مدل‌ها
full_models = """
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
    token = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    entry_price = Column(Float)
    entry_usd = Column(Float)
    regime = Column(String)
    return_1m = Column(Float, nullable=True)
    return_5m = Column(Float, nullable=True)
    return_15m = Column(Float, nullable=True)
    return_30m = Column(Float, nullable=True)
    return_1h = Column(Float, nullable=True)
    return_4h = Column(Float, nullable=True)
    return_24h = Column(Float, nullable=True)
    mfe = Column(Float, nullable=True)
    mae = Column(Float, nullable=True)
    win = Column(Boolean, nullable=True)
    __table_args__ = (
        Index('ix_wallet_perf_wallet_timestamp', 'wallet', 'timestamp'),
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
"""

write("src/storage/models.py", full_models)

print("running tests...")
res = subprocess.run([sys.executable, "-m", "pytest", "-q", "--disable-warnings"], cwd=ROOT)
if res.returncode != 0:
    print("tests failed")
    sys.exit(1)
print("tests passed")

subprocess.run(["git", "add", "-A"], cwd=ROOT, check=True)
subprocess.run(["git", "commit", "-m", "fix: restore full models.py with all tables"], cwd=ROOT, check=True)
subprocess.run(["git", "push", "origin", "main"], cwd=ROOT, check=True)
print("Fixed and committed.")
