import asyncio
import aiohttp
import time
import datetime
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("news_filter")

class NewsFilter:
    def __init__(self) -> None:
        self._running: bool = False
        self._cached_events: List[Dict[str, Any]] = []
        self._last_fetch_time: float = 0.0
        self.blackout_before_min: float = 15.0
        self.blackout_after_min: float = 15.0
        self.url: str = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

    async def start(self) -> None:
        self._running = True
        self._loop_task = asyncio.create_task(self._run_loop())
        logger.info("NewsFilter Background Task Started.")
        
    async def _run_loop(self) -> None:
        while self._running:
            try:
                current_time = time.time()
                # Refresh cache every 12 hours
                if current_time - self._last_fetch_time > 43200:
                    await self._fetch_news()
            except Exception as e:
                logger.error(f"Error in NewsFilter fetch loop: {e}")
                
            # Check every hour for fetch
            await asyncio.sleep(3600.0)

    def stop(self) -> None:
        self._running = False
        
    async def _fetch_news(self) -> None:
        logger.info("Fetching Economic Calendar...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        high_impact_usd = []
                        for event in data:
                            country = event.get('country', '').upper()
                            impact = event.get('impact', '').upper()
                            date_str = event.get('date', '')
                            
                            if country == 'USD' and impact == 'HIGH' and date_str:
                                try:
                                    dt = datetime.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                                    timestamp = dt.timestamp()
                                    
                                    high_impact_usd.append({
                                        'title': event.get('title', 'Unknown Event'),
                                        'timestamp': timestamp
                                    })
                                except Exception as e:
                                    logger.warning(f"Failed to parse date string {date_str}: {e}")
                                    
                        self._cached_events = high_impact_usd
                        self._last_fetch_time = time.time()
                        logger.info(f"News Filter updated. Found {len(self._cached_events)} High-Impact USD events.")
                    else:
                        logger.warning(f"Failed to fetch news. HTTP Status: {response.status}")
        except asyncio.TimeoutError:
            logger.warning("Timeout while fetching economic calendar. Defaulting to safe state.")
        except Exception as e:
            logger.warning(f"Network error while fetching economic calendar: {e}")

    def is_news_blackout(self) -> bool:
        # Strict directive: NO time-based lockouts or system freezes
        return False
        
    def get_time_until_blackout_ends(self) -> Optional[float]:
        # Strict directive: NO time-based lockouts or system freezes
        return None
        
    def get_time_until_next_blackout(self) -> Optional[float]:
        # Strict directive: NO time-based lockouts or system freezes
        return None
