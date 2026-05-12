import json
from typing import Any

from redis.asyncio import Redis


class RedisEventBus:
    def __init__(self, redis_url: str) -> None:
        self._client = Redis.from_url(redis_url, decode_responses=True)

    async def publish_stream(self, stream_name: str, payload: dict[str, Any]) -> str:
        return await self._client.xadd(stream_name, {"payload": json.dumps(payload)})

    async def publish_channel(self, channel_name: str, payload: dict[str, Any]) -> int:
        return await self._client.publish(channel_name, json.dumps(payload))

    async def close(self) -> None:
        await self._client.aclose()
