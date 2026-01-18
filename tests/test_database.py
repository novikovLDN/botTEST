import pytest
from unittest.mock import MagicMock, AsyncMock
import database

# Test Helper Functions
def test_safe_int():
    assert database.safe_int(10) == 10
    assert database.safe_int("10") == 10
    assert database.safe_int(None) == 0
    assert database.safe_int("invalid") == 0

def test_safe_float():
    assert database.safe_float(10.5) == 10.5
    assert database.safe_float("10.5") == 10.5
    assert database.safe_float(None) == 0.0
    assert database.safe_float("invalid") == 0.0

# Mock DB Logic
@pytest.mark.asyncio
async def test_increase_balance(mocker):
    # Mock the pool (AsyncMock for get_pool return value, but acquire is synchronous returning context manager)
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_transaction = AsyncMock()
    
    # Configure context managers
    # pool.acquire() returns an async context manager
    mock_acquire_ctx = AsyncMock()
    mock_acquire_ctx.__aenter__.return_value = mock_conn
    mock_acquire_ctx.__aexit__.return_value = None
    mock_pool.acquire.return_value = mock_acquire_ctx

    # conn.transaction() returns an async context manager, but the method itself is synchronous
    mock_transaction_ctx = AsyncMock()
    mock_transaction_ctx.__aenter__.return_value = mock_transaction
    mock_transaction_ctx.__aexit__.return_value = None
    mock_conn.transaction = MagicMock(return_value=mock_transaction_ctx)
    
    # Patch get_pool to return our mock pool
    # get_pool is async, so it returns a coroutine that returns result
    mocker.patch('database.get_pool', new_callable=AsyncMock, return_value=mock_pool)
    
    # Run the function
    result = await database.increase_balance(
        telegram_id=123,
        amount=100.0,
        source="test",
        description="test deposit"
    )
    
    # Assertions
    assert result is True
    
    # Verify SQL execution
    # Balance update (amount converted to kopecks: 100.0 * 100 = 10000)
    mock_conn.execute.assert_any_call(
        "UPDATE users SET balance = balance + $1 WHERE telegram_id = $2",
        10000, 123
    )
    
    # Transaction log
    assert mock_conn.execute.call_count == 2
