import asyncio
import time
from src.core.news_filter import NewsFilter

async def main():
    nf = NewsFilter()
    await nf._fetch_news()
    is_blackout = nf.is_news_blackout()
    ends_in = nf.get_time_until_blackout_ends()
    next_blackout = nf.get_time_until_next_blackout()
    print(f"Events loaded: {len(nf._cached_events)}")
    print(f"Is Blackout: {is_blackout}")
    print(f"Ends in: {ends_in}")
    print(f"Next blackout in: {next_blackout}")

if __name__ == "__main__":
    asyncio.run(main())
