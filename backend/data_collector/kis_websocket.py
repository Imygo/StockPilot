"""KIS 모의투자 웹소켓 연결: 직접 연결 및 초기 연결 재시도."""
import asyncio
from contextlib import asynccontextmanager
import logging

from websockets.asyncio.client import connect
from websockets.exceptions import InvalidHandshake, InvalidStatus

LOG = logging.getLogger(__name__)
PAPER_URL = "ws://ops.koreainvestment.com:31000/"


@asynccontextmanager
async def paper_connection(url, attempts=5):
    if url != PAPER_URL:
        raise ValueError("모의투자 웹소켓 주소만 허용합니다.")
    if attempts < 1:
        raise ValueError("연결 시도 횟수는 1 이상이어야 합니다.")
    ws = None
    for attempt in range(1, attempts + 1):
        LOG.warning("모의투자 웹소켓 직접 연결 시도: %s (%s/%s)", url, attempt, attempts)
        try:
            # websockets 15+의 시스템 프록시 자동 사용을 이 연결에서만 해제.
            ws = await connect(url, proxy=None, open_timeout=15,
                               close_timeout=5, ping_interval=None)
        except (OSError, TimeoutError, InvalidHandshake) as exc:
            LOG.warning("웹소켓 초기 연결 실패: %s: %s", type(exc).__name__, exc)
            if isinstance(exc, InvalidStatus) and exc.response.status_code in (400, 401, 403, 404):
                raise RuntimeError(
                    f"웹소켓 서버가 HTTP {exc.response.status_code}로 연결을 거절했습니다. "
                    "모의투자 서버 주소와 서버 상태를 확인하세요."
                ) from exc
            if attempt == attempts:
                raise RuntimeError(
                    f"모의투자 웹소켓 초기 연결 {attempts}회 실패: {url}. "
                    "서버 상태, 방화벽/VPN 및 TCP 31000 포트 접근을 확인하세요. "
                    "체결 수집은 시작되지 않았습니다."
                ) from exc
            delay = min(2 ** attempt, 16)
            LOG.warning("%s초 후 재시도합니다.", delay)
            await asyncio.sleep(delay)
        else:
            break
    LOG.warning("모의투자 웹소켓 연결 성공")
    try:
        # 수신 중 오류는 재시도하지 않는다: 공백이 있는 집계의 정상 완료를 방지.
        yield ws
    finally:
        await ws.close()
