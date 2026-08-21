#!/bin/bash
set -e

echo "🔧 اصلاح قطعی datetime در مدل‌ها..."

cd ~/Crypto_bot

# --------------------------------------------------------------------
# بازنویسی کامل models.py با import صحیح و استفاده از datetime.now(UTC)
# --------------------------------------------------------------------
cat > src/storage/models.py <<'EOF'
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, JSON, Index
from sqlalchemy.orm import declarative_base
from datetime import datetime, UTC

Base = declarative_base()

class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True)
    address = Column(String, nullable=False, unique=True)
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

    __table_args__ = (
        Index('ix_wallets_chain_address', 'chain', 'address'),
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

class BlockchainEvent(Base):
    """Raw/Normalized blockchain events for research/storage."""
    __tablename__ = "blockchain_events"

    id = Column(Integer, primary_key=True)
    chain = Column(String, nullable=False)
    network = Column(String, nullable=False)
    event_type = Column(String, nullable=False)  # block, transaction, log, transfer, swap
    block_number = Column(Integer, nullable=False)
    block_hash = Column(String)
    transaction_hash = Column(String)
    log_index = Column(Integer, default=0)
    data = Column(JSON, nullable=True)  # normalized data
    status = Column(String, default="pending")  # pending/confirmed/finalized/reorged
    timestamp = Column(DateTime, nullable=False)

    __table_args__ = (
        Index('ix_blockchain_events_chain_block', 'chain', 'block_number'),
        Index('ix_blockchain_events_tx', 'chain', 'transaction_hash'),
        Index('ix_blockchain_events_type', 'event_type'),
    )
EOF

# --------------------------------------------------------------------
# اجرای تست‌ها
# --------------------------------------------------------------------
echo "🧪 اجرای تست‌ها..."
if ! pytest -q --disable-warnings; then
    echo "❌ تست‌ها شکست خوردند. فایل را بررسی کنید."
    exit 1
fi

echo "✅ تست‌ها موفق بودند."

# --------------------------------------------------------------------
# Commit و Push
# --------------------------------------------------------------------
echo "📦 Commit و Push اصلاح datetime..."
git add -A
git commit -m "fix: correct timezone-aware datetime import and defaults" || echo "No changes to commit"
git push origin main

echo "🎉 اصلاح datetime انجام شد و به گیت‌هاب Push شد."
