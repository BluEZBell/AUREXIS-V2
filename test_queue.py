import asyncio

async def consumer(q):
    while True:
        item = await q.get()
        print(f"Consumed {item}")
        q.task_done()

async def main():
    q = asyncio.Queue()
    asyncio.create_task(consumer(q))
    
    for i in range(5):
        await q.put(i)
        # We await something that returns immediately
        await asyncio.gather(asyncio.sleep(0, result=1))
        print(f"Produced {i}")
        
    await q.join()
    print("Done")

asyncio.run(main())
