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
