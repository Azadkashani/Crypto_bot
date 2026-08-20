import pytest
from src.blockchain.base import BaseBlockchainAdapter

def test_base_adapter_is_abstract():
    with pytest.raises(TypeError):
        BaseBlockchainAdapter()
