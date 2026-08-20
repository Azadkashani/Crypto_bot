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
