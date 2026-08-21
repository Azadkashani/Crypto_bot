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
