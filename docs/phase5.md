# Phase 5: DEX Swap Detection & Real BUY/SELL Classification

## Overview
This phase implements the detection of DEX swap events (starting with Uniswap V2 on Ethereum), parsing them into normalized swap records, identifying the trader wallet, and classifying each swap as BUY, SELL, or UNKNOWN with a confidence score.

## Key Components
- `src/dex/base.py`: BaseDEXAdapter interface.
- `src/dex/registry.py`: DEXRegistry to manage adapters.
- `src/dex/ethereum/uniswap.py`: Uniswap V2 adapter.
- `src/dex/parsers/swap_parser.py`: SwapParser engine.
- `src/dex/parsers/price_resolver.py`: Placeholder for price resolution.
- Database table `swaps` for normalized swap events.

## Classification Logic
- BUY: stablecoin/native/wrapped native -> token.
- SELL: token -> stablecoin/native/wrapped native.
- UNKNOWN: ambiguous, multi-hop, token-to-token without clear direction.

## Confidence Scoring
Based on evidence: valid swap, clear pool, clear trader, known token direction, stable/native involvement.

## False Positive Prevention
Negative tests ensure large transfers, liquidity events, CEX transfers, etc., are not misclassified as BUY/SELL.
