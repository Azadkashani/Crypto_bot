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
