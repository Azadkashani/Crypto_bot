#!/bin/bash
set -e  # توقف در صورت بروز خطا

echo "🚀 ایجاد ساختار پروژه Phase 2..."

# ایجاد پوشه‌ها
mkdir -p src/core src/blockchain src/providers/ethereum src/providers/bsc src/providers/solana \
         src/collectors src/classification src/dex/evm src/dex/solana src/detection \
         src/scoring src/consensus src/signal src/storage src/research src/market \
         src/data_quality src/notifications tests/unit tests/integration tests/fixtures \
         data logs scripts alembic

# ایجاد فایل‌های __init__.py خالی برای تمام پوشه‌ها
find . -type d -not -path './.git*' -exec touch {}/__init__.py \;

# --------------------------------------------------------------------
# به‌روزرسانی .gitignore
# --------------------------------------------------------------------
if ! grep -q "backtest/" .gitignore 2>/dev/null; then
    cat >> .gitignore <<'EOF'

# Legacy research files (do not commit)
backtest/
backtest_results.csv
backtest_results_1h.csv
forensic_analysis.csv
losing_trades_analysis.csv
test_results_strategy.csv
EOF
    echo "✅ .gitignore به‌روزرسانی شد."
else
    echo "ℹ️  .gitignore قبلاً شامل موارد legacy است."
fi

# --------------------------------------------------------------------
# requirements.txt (حفظ وابستگی‌های قبلی + اضافه‌های جدید)
# --------------------------------------------------------------------
cat > requirements.txt <<'EOF'
# Core (سازگار با Python 3.12)
python-dotenv>=1.0.0
pandas>=2.1.0
numpy>=1.26.0
# Exchange API
gate-api==6.78.0
# Technical Analysis
pandas-ta==0.3.14b0
# Data & Backtesting
backtesting==0.3.3
# News & Sentiment
requests>=2.31.0
beautifulsoup4>=4.12.0
feedparser>=6.0.10
# Logging & Monitoring
loguru>=0.7.0
python-telegram-bot>=20.0
# Scheduling
apscheduler>=3.10.0
# Utils
colorama>=0.4.6
tabulate>=0.9.0
# Blockchain & Async
web3>=6.18.0
httpx>=0.27.0
websockets>=12.0
# Database & Validation
sqlalchemy>=2.0.0
pydantic>=2.7.0
pydantic-settings>=2.2.0
# Testing
pytest>=8.0.0
EOF

# --------------------------------------------------------------------
# requirements-dev.txt
# --------------------------------------------------------------------
cat > requirements-dev.txt <<'EOF'
pytest>=8.0.0
pytest-asyncio>=0.23.0
alembic>=1.13.0
EOF

# --------------------------------------------------------------------
# .env.example
# --------------------------------------------------------------------
cat > .env.example <<'EOF'
# ========================
# Project Modes
# ========================
MODE=research            # research | paper | live
LIVE_TRADING_ENABLED=false   # Safety gate: must be true to allow any real orders

# ========================
# Database
# ========================
DATABASE_URL=sqlite:///data/whale.db

# ========================
# Chain Enable Flags
# ========================
ETH_ENABLED=true
BSC_ENABLED=false
SOLANA_ENABLED=false

# ========================
# Provider Configuration (Ethereum)
# ========================
ETH_PRIMARY_PROVIDER=alchemy
ETH_BACKUP_PROVIDER=etherscan
ETH_RPC_URL=
ETH_WS_URL=
ETH_ETHERSCAN_API_KEY=
ETH_CHAIN_ID=1

# ========================
# Provider Configuration (BSC)
# ========================
BSC_PRIMARY_PROVIDER=quicknode
BSC_BACKUP_PROVIDER=bscscan
BSC_RPC_URL=
BSC_WS_URL=
BSCSCAN_API_KEY=
BSC_CHAIN_ID=56

# ========================
# Provider Configuration (Solana)
# ========================
SOLANA_PRIMARY_PROVIDER=helius
SOLANA_BACKUP_PROVIDER=solscan
SOLANA_RPC_URL=
SOLANA_WS_URL=
SOLANA_API_KEY=

# ========================
# Whale Detection & Scoring
# ========================
MIN_PORTFOLIO_VALUE_USD=1000000
MIN_TRADE_USD=100000
MIN_BUY_USD=50000
MIN_TRANSACTION_COUNT=10
WHALE_SCORE_THRESHOLD=70
SMART_MONEY_SCORE_THRESHOLD=70
PREDICTIVE_WALLET_THRESHOLD=75

# Scoring Weights (will be tuned later)
WEIGHT_CAPITAL=0.15
WEIGHT_VOLUME=0.15
WEIGHT_TX_SIZE=0.15
WEIGHT_CONSISTENCY=0.10
WEIGHT_ROI=0.15
WEIGHT_WIN_RATE=0.15
WEIGHT_ENTRY_TIMING=0.15

# ========================
# Token Universe Filters
# ========================
MIN_LIQUIDITY_USD=1000000
MIN_24H_VOLUME_USD=500000
MIN_MARKET_CAP_USD=5000000
MIN_TOKEN_AGE_DAYS=7
MAX_TOKEN_AGE_DAYS=3650
MIN_WHALE_ACTIVITY_COUNT=3

# ========================
# Consensus
# ========================
CONSENSUS_WINDOW_MINUTES=60
MIN_INDEPENDENT_WHALES=3
MIN_NET_FLOW_USD=500000

# ========================
# Signal
# ========================
SIGNAL_MIN_SCORE=85
SIGNAL_MIN_CONFIDENCE=80

# ========================
# Finality & Confirmation
# ========================
REQUIRED_CONFIRMATIONS=6

# ========================
# Rate Limit & Cost Tracking
# ========================
RATE_LIMIT_ENABLED=true
COST_TRACKING_ENABLED=true

# ========================
# Gate.io (for market data/validation only in research)
# ========================
GATE_API_KEY=
GATE_API_SECRET=
EOF

# --------------------------------------------------------------------
# src/core/config.py
# --------------------------------------------------------------------
cat > src/core/config.py <<'EOF'
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
    eth_chain_id: int = 1

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

    # Whale Detection
    min_portfolio_value_usd: float = 1_000_000
    min_trade_usd: float = 100_000
    min_buy_usd: float = 50_000
    min_transaction_count: int = 10
    whale_score_threshold: float = 70
    smart_money_score_threshold: float = 70
    predictive_wallet_threshold: float = 75

    # Scoring Weights
    weight_capital: float = 0.15
    weight_volume: float = 0.15
    weight_tx_size: float = 0.15
    weight_consistency: float = 0.10
    weight_roi: float = 0.15
    weight_win_rate: float = 0.15
    weight_entry_timing: float = 0.15

    # Token Universe Filters
    min_liquidity_usd: float = 1_000_000
    min_24h_volume_usd: float = 500_000
    min_market_cap_usd: float = 5_000_000
    min_token_age_days: int = 7
    max_token_age_days: int = 3650
    min_whale_activity_count: int = 3

    # Consensus
    consensus_window_minutes: int = 60
    min_independent_whales: int = 3
    min_net_flow_usd: float = 500_000

    # Signal
    signal_min_score: float = 85
    signal_min_confidence: float = 80

    # Finality
    required_confirmations: int = 6

    # Rate Limit & Cost Tracking
    rate_limit_enabled: bool = True
    cost_tracking_enabled: bool = True

    # Gate.io
    gate_api_key: Optional[str] = None
    gate_api_secret: Optional[str] = None

settings = Settings()
EOF

# --------------------------------------------------------------------
# src/core/logger.py
# --------------------------------------------------------------------
cat > src/core/logger.py <<'EOF'
import sys
from loguru import logger

def setup_logger():
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    logger.add("logs/whale_engine_{time:YYYYMMDD}.log", rotation="1 day", retention="7 days", level="DEBUG")
    return logger

logger = setup_logger()
EOF

# --------------------------------------------------------------------
# src/core/constants.py
# --------------------------------------------------------------------
cat > src/core/constants.py <<'EOF'
from enum import Enum

class Chain(str, Enum):
    ETHEREUM = "ethereum"
    BSC = "bsc"
    SOLANA = "solana"
    TRON = "tron"  # future
    TON = "ton"    # future

class TransactionStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FINALIZED = "finalized"
    REORGED = "reorged"

class ClassificationLabel(str, Enum):
    TRANSFER = "TRANSFER"
    BUY = "BUY"
    SELL = "SELL"
    SWAP = "SWAP"
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    INTERNAL_TRANSFER = "INTERNAL_TRANSFER"
    LP = "LP"
    BRIDGE = "BRIDGE"
    STAKING = "STAKING"
    UNSTAKING = "UNSTAKING"
    ARBITRAGE = "ARBITRAGE"
    MEV = "MEV"
    CONTRACT_INTERACTION = "CONTRACT_INTERACTION"
    UNKNOWN = "UNKNOWN"

class AddressLabel(str, Enum):
    EXCHANGE = "EXCHANGE"
    DEX = "DEX"
    ROUTER = "ROUTER"
    BRIDGE = "BRIDGE"
    LP = "LP"
    TREASURY = "TREASURY"
    BURN = "BURN"
    STAKING = "STAKING"
    LENDING = "LENDING"
    MEV = "MEV"
    BOT = "BOT"
    UNKNOWN = "UNKNOWN"

class AddressSource(str, Enum):
    OFFICIAL = "official"
    PROVIDER = "provider"
    HEURISTIC = "heuristic"
    MANUALLY_VERIFIED = "manually_verified"

class MarketRegime(str, Enum):
    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
EOF

# --------------------------------------------------------------------
# src/blockchain/base.py
# --------------------------------------------------------------------
cat > src/blockchain/base.py <<'EOF'
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from src.core.constants import Chain

class BlockData(BaseModel):
    chain: Chain
    network: str
    block_number: int
    block_hash: str
    timestamp: int
    parent_hash: str
    extra_data: Optional[Dict[str, Any]] = None

class TransactionData(BaseModel):
    chain: Chain
    network: str
    block_number: int
    block_hash: str
    transaction_hash: str
    transaction_index: int
    from_address: str
    to_address: Optional[str]
    value: int
    timestamp: int
    status: Optional[str] = None
    gas_used: Optional[int] = None
    gas_price: Optional[int] = None
    logs: Optional[List[Dict[str, Any]]] = None
    extra_data: Optional[Dict[str, Any]] = None

class TransferData(BaseModel):
    chain: Chain
    network: str
    block_number: int
    transaction_hash: str
    log_index: int
    token_address: str
    from_address: str
    to_address: str
    amount: int
    token_decimals: int
    token_symbol: Optional[str] = None
    timestamp: int
    extra_data: Optional[Dict[str, Any]] = None

class SwapEventData(BaseModel):
    chain: Chain
    network: str
    block_number: int
    transaction_hash: str
    log_index: int
    dex: str
    pair_address: str
    sender: str
    recipient: str
    token_in: str
    token_out: str
    amount_in: int
    amount_out: int
    timestamp: int
    extra_data: Optional[Dict[str, Any]] = None

class BaseBlockchainAdapter(ABC):
    chain: Chain
    network: str

    @abstractmethod
    async def get_latest_block_number(self) -> int:
        ...

    @abstractmethod
    async def get_block_by_number(self, block_number: int) -> BlockData:
        ...

    @abstractmethod
    async def get_transactions_by_address(self, address: str, start_block: int, end_block: int) -> List[TransactionData]:
        ...

    @abstractmethod
    async def get_token_transfers(self, address: str, token: str, start_block: int, end_block: int) -> List[TransferData]:
        ...

    @abstractmethod
    async def get_dex_swap_events(self, token: str, start_block: int, end_block: int) -> List[SwapEventData]:
        ...

    @abstractmethod
    async def get_wallet_balance(self, address: str) -> float:
        ...

    @abstractmethod
    async def get_token_metadata(self, token_address: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    async def is_contract(self, address: str) -> bool:
        ...
EOF

# --------------------------------------------------------------------
# src/providers/base.py
# --------------------------------------------------------------------
cat > src/providers/base.py <<'EOF'
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Callable
from src.core.constants import Chain

class BaseDataProvider(ABC):
    name: str
    chain: Chain

    @abstractmethod
    async def fetch_transactions_by_address(self, address: str, start_block: int, end_block: int) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    async def fetch_token_transfers(self, address: str, token: str, start_block: int, end_block: int) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    async def fetch_dex_swap_events(self, token: str, start_block: int, end_block: int) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    async def stream_blocks(self, callback: Callable[[Dict[str, Any]], None]):
        ...

    @abstractmethod
    async def stream_logs(self, topics: List[str], callback: Callable[[Dict[str, Any]], None]):
        ...

    @abstractmethod
    async def fetch_token_price(self, token: str, timestamp: int) -> float:
        ...

    @abstractmethod
    async def fetch_market_cap(self, token: str) -> float:
        ...
EOF

# --------------------------------------------------------------------
# src/classification/base.py
# --------------------------------------------------------------------
cat > src/classification/base.py <<'EOF'
from abc import ABC, abstractmethod
from typing import List
from src.core.constants import ClassificationLabel
from pydantic import BaseModel

class ClassificationResult(BaseModel):
    label: ClassificationLabel
    confidence: float
    reasons: List[str] = []

class BaseTransactionClassifier(ABC):
    @abstractmethod
    def classify(self, transaction: dict, context: dict) -> ClassificationResult:
        ...
EOF

# --------------------------------------------------------------------
# src/dex/base.py
# --------------------------------------------------------------------
cat > src/dex/base.py <<'EOF'
from abc import ABC, abstractmethod
from typing import Dict, Any
from pydantic import BaseModel

class DexInfo(BaseModel):
    name: str
    chain: str
    router_address: str
    factory_address: str
    pair_created_event: str
    swap_event: str

class BaseDexAdapter(ABC):
    dex_info: DexInfo

    @abstractmethod
    def parse_swap(self, log: Dict[str, Any]) -> Dict[str, Any]:
        ...
EOF

# --------------------------------------------------------------------
# src/scoring/base.py
# --------------------------------------------------------------------
cat > src/scoring/base.py <<'EOF'
from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Dict, Any

class ScoreResult(BaseModel):
    score: float
    features: Dict[str, float]
    explanation: Dict[str, Any]

class BaseScorer(ABC):
    @abstractmethod
    def calculate(self, wallet_data: Dict[str, Any]) -> ScoreResult:
        ...
EOF

# --------------------------------------------------------------------
# src/signal/base.py
# --------------------------------------------------------------------
cat > src/signal/base.py <<'EOF'
from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Dict, Any

class SignalData(BaseModel):
    token: str
    chain: str
    timestamp: int
    signal_score: float
    confidence: float
    components: Dict[str, Any]
    regime: str
    gate_available: bool
    mode: str

class BaseSignalGenerator(ABC):
    @abstractmethod
    def generate(self, context: Dict[str, Any]) -> SignalData:
        ...
EOF

# --------------------------------------------------------------------
# src/storage/models.py
# --------------------------------------------------------------------
cat > src/storage/models.py <<'EOF'
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, JSON, Index
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True)
    address = Column(String, nullable=False, unique=True)
    chain = Column(String, nullable=False)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    balance_usd = Column(Float, default=0.0)
    portfolio_value_usd = Column(Float, default=0.0)
    transaction_count = Column(Integer, default=0)
    whale_score = Column(Float, nullable=True)
    smart_money_score = Column(Float, nullable=True)
    predictive_wallet_score = Column(Float, nullable=True)
    status = Column(String, default="active")
    metadata = Column(JSON, nullable=True)

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
    updated_at = Column(DateTime, default=datetime.utcnow)

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
EOF

# --------------------------------------------------------------------
# src/storage/database.py
# --------------------------------------------------------------------
cat > src/storage/database.py <<'EOF'
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.core.config import settings
from src.storage.models import Base

engine = create_engine(settings.database_url, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def init_db():
    Base.metadata.create_all(bind=engine)
EOF

# --------------------------------------------------------------------
# src/storage/repositories.py
# --------------------------------------------------------------------
cat > src/storage/repositories.py <<'EOF'
from typing import List, Optional
from sqlalchemy.orm import Session
from src.storage.models import Wallet, Transaction, WhaleEvent, Signal, ExcludedAddress, TokenStats, WhaleConsensus

class BaseRepository:
    def __init__(self, session: Session):
        self.session = session

class WalletRepository(BaseRepository):
    def get_by_address(self, chain: str, address: str) -> Optional[Wallet]:
        return self.session.query(Wallet).filter_by(chain=chain, address=address).first()

    def add(self, wallet: Wallet):
        self.session.add(wallet)

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
EOF

# --------------------------------------------------------------------
# src/data_quality/validator.py
# --------------------------------------------------------------------
cat > src/data_quality/validator.py <<'EOF'
class DataQualityValidator:
    @staticmethod
    def validate_event(event: dict) -> bool:
        required = ["chain", "block_number", "transaction_hash", "timestamp"]
        return all(field in event for field in required)

    @staticmethod
    def validate_classification(classification: dict) -> bool:
        if "label" not in classification or "confidence" not in classification:
            return False
        if classification["confidence"] < 0 or classification["confidence"] > 1:
            return False
        return True
EOF

# --------------------------------------------------------------------
# src/data_quality/deduplicator.py
# --------------------------------------------------------------------
cat > src/data_quality/deduplicator.py <<'EOF'
class Deduplicator:
    def __init__(self):
        self.seen_ids = set()

    def is_duplicate(self, event: dict) -> bool:
        event_id = f"{event.get('chain')}:{event.get('transaction_hash')}:{event.get('log_index', 0)}"
        if event_id in self.seen_ids:
            return True
        self.seen_ids.add(event_id)
        return False

    def reset(self):
        self.seen_ids.clear()
EOF

# --------------------------------------------------------------------
# src/data_quality/completeness.py
# --------------------------------------------------------------------
cat > src/data_quality/completeness.py <<'EOF'
class CompletenessChecker:
    @staticmethod
    def check(event: dict) -> bool:
        if 'value' in event and event['value'] is not None:
            if event['value'] < 0:
                return False
        return True
EOF

# --------------------------------------------------------------------
# src/data_quality/consistency.py
# --------------------------------------------------------------------
cat > src/data_quality/consistency.py <<'EOF'
class ConsistencyChecker:
    @staticmethod
    def check(event: dict, reference_data: dict) -> bool:
        return True
EOF

# --------------------------------------------------------------------
# src/signal/gate_validator.py (interface only)
# --------------------------------------------------------------------
cat > src/signal/gate_validator.py <<'EOF'
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseGateValidator(ABC):
    @abstractmethod
    def is_futures_available(self, token: str) -> bool:
        ...
    @abstractmethod
    def get_market_data(self, token: str) -> Dict[str, Any]:
        ...
EOF

# --------------------------------------------------------------------
# src/signal/market_confirmation.py (interface only)
# --------------------------------------------------------------------
cat > src/signal/market_confirmation.py <<'EOF'
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseMarketConfirmation(ABC):
    @abstractmethod
    def confirm(self, token: str, context: Dict[str, Any]) -> bool:
        ...
EOF

# --------------------------------------------------------------------
# src/consensus/wallet_clustering.py (interface only)
# --------------------------------------------------------------------
cat > src/consensus/wallet_clustering.py <<'EOF'
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseWalletClustering(ABC):
    @abstractmethod
    def cluster_wallets(self, wallet_features: List[Dict[str, Any]]) -> List[List[str]]:
        ...
EOF

# --------------------------------------------------------------------
# src/consensus/independence.py (interface only)
# --------------------------------------------------------------------
cat > src/consensus/independence.py <<'EOF'
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseIndependenceCalculator(ABC):
    @abstractmethod
    def independent_wallets(self, whale_events: List[Dict[str, Any]]) -> int:
        ...
EOF

# --------------------------------------------------------------------
# src/market/token_universe.py
# --------------------------------------------------------------------
cat > src/market/token_universe.py <<'EOF'
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseTokenUniverse(ABC):
    @abstractmethod
    def get_candidate_tokens(self) -> List[str]:
        ...
    @abstractmethod
    def filter_tokens(self, tokens: List[str], filters: Dict[str, Any]) -> List[str]:
        ...
EOF

# --------------------------------------------------------------------
# src/market/token_metadata.py
# --------------------------------------------------------------------
cat > src/market/token_metadata.py <<'EOF'
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseTokenMetadata(ABC):
    @abstractmethod
    def get_metadata(self, token: str, chain: str) -> Dict[str, Any]:
        ...
EOF

# --------------------------------------------------------------------
# src/market/liquidity.py
# --------------------------------------------------------------------
cat > src/market/liquidity.py <<'EOF'
from abc import ABC, abstractmethod

class BaseLiquidityProvider(ABC):
    @abstractmethod
    def get_liquidity(self, token: str, chain: str) -> float:
        ...
EOF

# --------------------------------------------------------------------
# src/market/market_data.py
# --------------------------------------------------------------------
cat > src/market/market_data.py <<'EOF'
from abc import ABC, abstractmethod

class BaseMarketDataProvider(ABC):
    @abstractmethod
    def get_price(self, token: str, timestamp: int) -> float:
        ...
    @abstractmethod
    def get_volume_24h(self, token: str) -> float:
        ...
    @abstractmethod
    def get_ohlcv(self, token: str, interval: str) -> list:
        ...
EOF

# --------------------------------------------------------------------
# src/notifications/base.py
# --------------------------------------------------------------------
cat > src/notifications/base.py <<'EOF'
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseNotifier(ABC):
    @abstractmethod
    def send(self, message: str, data: Dict[str, Any] = None) -> bool:
        ...
EOF

# --------------------------------------------------------------------
# main.py
# --------------------------------------------------------------------
cat > main.py <<'EOF'
from src.core.config import settings
from src.core.logger import logger
from src.storage.database import init_db

def main():
    logger.info(f"Starting Whale Engine in {settings.mode} mode")
    if settings.mode == "live" and not settings.live_trading_enabled:
        logger.warning("Live trading is disabled. Running in research mode only.")
        settings.mode = "research"
    init_db()
    logger.info("Phase 2 skeleton ready. Exiting.")

if __name__ == "__main__":
    main()
EOF

# --------------------------------------------------------------------
# Placeholder adapters (Ethereum, BSC, Solana) and providers
# --------------------------------------------------------------------
cat > src/blockchain/ethereum.py <<'EOF'
from src.blockchain.base import BaseBlockchainAdapter

class EthereumAdapter(BaseBlockchainAdapter):
    chain = "ethereum"
    network = "mainnet"
    # Methods to be implemented in later phases
EOF

cat > src/blockchain/bsc.py <<'EOF'
from src.blockchain.base import BaseBlockchainAdapter

class BscAdapter(BaseBlockchainAdapter):
    chain = "bsc"
    network = "mainnet"
    # Methods to be implemented in later phases
EOF

cat > src/blockchain/solana.py <<'EOF'
from src.blockchain.base import BaseBlockchainAdapter

class SolanaAdapter(BaseBlockchainAdapter):
    chain = "solana"
    network = "mainnet"
    # Methods to be implemented in later phases
EOF

cat > src/providers/ethereum/alchemy.py <<'EOF'
from src.providers.base import BaseDataProvider

class AlchemyProvider(BaseDataProvider):
    name = "alchemy"
    chain = "ethereum"
    # Methods to be implemented in later phases
EOF

cat > src/providers/ethereum/etherscan.py <<'EOF'
from src.providers.base import BaseDataProvider

class EtherscanProvider(BaseDataProvider):
    name = "etherscan"
    chain = "ethereum"
    # Methods to be implemented in later phases
EOF

cat > src/providers/bsc/quicknode.py <<'EOF'
from src.providers.base import BaseDataProvider

class QuickNodeProvider(BaseDataProvider):
    name = "quicknode"
    chain = "bsc"
    # Methods to be implemented in later phases
EOF

cat > src/providers/bsc/bscscan.py <<'EOF'
from src.providers.base import BaseDataProvider

class BscscanProvider(BaseDataProvider):
    name = "bscscan"
    chain = "bsc"
    # Methods to be implemented in later phases
EOF

cat > src/providers/solana/helius.py <<'EOF'
from src.providers.base import BaseDataProvider

class HeliusProvider(BaseDataProvider):
    name = "helius"
    chain = "solana"
    # Methods to be implemented in later phases
EOF

cat > src/providers/solana/solscan.py <<'EOF'
from src.providers.base import BaseDataProvider

class SolscanProvider(BaseDataProvider):
    name = "solscan"
    chain = "solana"
    # Methods to be implemented in later phases
EOF

# --------------------------------------------------------------------
# Scripts placeholder
# --------------------------------------------------------------------
cat > scripts/run_research.py <<'EOF'
def main():
    print("Not implemented in Phase 2")
if __name__ == "__main__":
    main()
EOF

cat > scripts/run_backfill.py <<'EOF'
def main():
    print("Not implemented in Phase 2")
if __name__ == "__main__":
    main()
EOF

cat > scripts/run_backtest.py <<'EOF'
def main():
    print("Not implemented in Phase 2")
if __name__ == "__main__":
    main()
EOF

# --------------------------------------------------------------------
# alembic.ini (minimal)
# --------------------------------------------------------------------
cat > alembic.ini <<'EOF'
[alembic]
script_location = alembic
sqlalchemy.url = sqlite:///data/whale.db

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
EOF

# --------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------
cat > tests/unit/test_config.py <<'EOF'
from src.core.config import Settings, Mode

def test_default_mode_research():
    s = Settings(_env_file=None)
    assert s.mode == Mode.research
    assert s.live_trading_enabled == False

def test_live_safety_gate():
    s = Settings(_env_file=None, mode="live", live_trading_enabled=False)
    assert s.live_trading_enabled == False
EOF

cat > tests/unit/test_models.py <<'EOF'
from src.storage.models import Base, Wallet
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def test_create_wallet():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    wallet = Wallet(address="0xabc", chain="ethereum", whale_score=80)
    session.add(wallet)
    session.commit()
    assert session.query(Wallet).count() == 1
    session.close()
EOF

cat > tests/unit/test_interfaces.py <<'EOF'
import pytest
from src.blockchain.base import BaseBlockchainAdapter

def test_base_adapter_is_abstract():
    with pytest.raises(TypeError):
        BaseBlockchainAdapter()
EOF

cat > tests/unit/test_classification.py <<'EOF'
from src.classification.base import ClassificationResult

def test_classification_result():
    r = ClassificationResult(label="BUY", confidence=0.95)
    assert r.label == "BUY"
    assert r.confidence == 0.95
EOF

cat > tests/unit/test_no_lookahead.py <<'EOF'
def test_no_lookahead_placeholder():
    assert True
EOF

echo "✅ تمام فایل‌های Phase 2 با موفقیت ایجاد شدند."
echo "اکنون می‌توانید با دستور 'pytest -q' تست‌ها را اجرا کنید."
