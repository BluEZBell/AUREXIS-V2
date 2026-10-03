import os
import asyncio
import aiosqlite
import logging

def setup_maintenance_logger():
    logger = logging.getLogger("db_maintenance")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    return logger

logger = setup_maintenance_logger()

TARGET_DBS = [
    "db/aurexis_ledger.db",
    "db/aurexis_quant_lake.db",
    "ledger_8000.db"
]

def get_file_size_mb(filepath: str) -> float:
    if os.path.exists(filepath):
        return os.path.getsize(filepath) / (1024 * 1024)
    return 0.0

async def maintain_database(db_path: str):
    if not os.path.exists(db_path):
        logger.warning(f"Database not found, skipping: {db_path}")
        return

    wal_path = f"{db_path}-wal"
    shm_path = f"{db_path}-shm"

    size_db_before = get_file_size_mb(db_path)
    size_wal_before = get_file_size_mb(wal_path)
    size_shm_before = get_file_size_mb(shm_path)
    total_before = size_db_before + size_wal_before + size_shm_before

    logger.info(f"--- Processing {db_path} ---")
    logger.info(f"Before: DB: {size_db_before:.3f} MB, WAL: {size_wal_before:.3f} MB, SHM: {size_shm_before:.3f} MB | Total: {total_before:.3f} MB")

    try:
        async with aiosqlite.connect(db_path) as db:
            # Checkpoint the WAL file (TRUNCATE merges and truncates the WAL file to zero size)
            logger.info(f"Executing PRAGMA wal_checkpoint(TRUNCATE) on {db_path}...")
            await db.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            await db.commit()

            # Vacuum the main database file to reclaim space
            logger.info(f"Executing VACUUM on {db_path}...")
            await db.execute("VACUUM;")
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to maintain {db_path}: {e}")
        return

    size_db_after = get_file_size_mb(db_path)
    size_wal_after = get_file_size_mb(wal_path)
    size_shm_after = get_file_size_mb(shm_path)
    total_after = size_db_after + size_wal_after + size_shm_after
    
    space_saved = total_before - total_after

    logger.info(f"After:  DB: {size_db_after:.3f} MB, WAL: {size_wal_after:.3f} MB, SHM: {size_shm_after:.3f} MB | Total: {total_after:.3f} MB")
    logger.info(f"Space Reclaimed: {space_saved:.3f} MB")
    logger.info("-" * 40)

async def main():
    logger.info("Starting Institutional Database Maintenance...")
    for db_path in TARGET_DBS:
        await maintain_database(db_path)
    logger.info("Database Maintenance Complete.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Maintenance aborted by user.")
