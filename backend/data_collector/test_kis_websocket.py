import unittest
from unittest.mock import AsyncMock, patch
from websockets.exceptions import InvalidMessage
import kis_websocket as transport


class ConnectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_http_then_success(self):
        ws = AsyncMock()
        with patch.object(transport, "connect", new=AsyncMock(
                side_effect=[InvalidMessage("did not receive a valid HTTP response"), ws])) as connect, \
             patch.object(transport.asyncio, "sleep", new=AsyncMock()) as sleep:
            async with transport.paper_connection(transport.PAPER_URL) as actual:
                self.assertIs(actual, ws)
            self.assertEqual(connect.await_count, 2)
            self.assertIsNone(connect.call_args.kwargs["proxy"])
            sleep.assert_awaited_once_with(2)
            ws.close.assert_awaited_once()

    async def test_exhaustion_does_not_enter_collection(self):
        with patch.object(transport, "connect", new=AsyncMock(side_effect=OSError("unreachable"))) as connect, \
             patch.object(transport.asyncio, "sleep", new=AsyncMock()):
            with self.assertRaisesRegex(RuntimeError, "수집은 시작되지"):
                async with transport.paper_connection(transport.PAPER_URL):
                    self.fail("must not enter collection")
            self.assertEqual(connect.await_count, 5)

    async def test_receive_failure_is_not_retried(self):
        ws = AsyncMock()
        with patch.object(transport, "connect", new=AsyncMock(return_value=ws)) as connect:
            with self.assertRaisesRegex(ConnectionError, "lost"):
                async with transport.paper_connection(transport.PAPER_URL):
                    raise ConnectionError("lost")
            connect.assert_awaited_once()
            ws.close.assert_awaited_once()

    async def test_live_endpoint_rejected(self):
        with patch.object(transport, "connect", new=AsyncMock()) as connect:
            with self.assertRaises(ValueError):
                async with transport.paper_connection("ws://ops.koreainvestment.com:21000/tryitout"):
                    self.fail("live connection")
            connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
