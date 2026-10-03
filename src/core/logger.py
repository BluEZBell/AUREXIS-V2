import logging
import logging.handlers
import queue
import sys
import threading
from typing import Optional

_log_queue_listener: Optional[logging.handlers.QueueListener] = None
_global_queue_handler: Optional[logging.Handler] = None
_logger_lock = threading.Lock()

class SafeRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """
    RotatingFileHandler that swallows exceptions (like disk full) silently
    to prevent crashing the trading architecture.
    """
    def handleError(self, record: logging.LogRecord) -> None:
        # Task 3: Fail silently and gracefully bypass file writing
        pass

class SafeQueueHandler(logging.handlers.QueueHandler):
    """
    QueueHandler that fails silently if placing into the queue encounters fatal exceptions.
    """
    def handleError(self, record: logging.LogRecord) -> None:
        pass

def setup_async_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Task 1: ASYNC LOG ROTATION
    Task 2: I/O OFFLOADING
    Task 3: FATAL EXCEPTION HANDLING
    """
    global _log_queue_listener
    global _global_queue_handler
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    with _logger_lock:
        if logger.handlers:
            return logger
            
        if _global_queue_handler is None:
            formatter = logging.Formatter(
                fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )

            # Task 2: Unbounded queue
            log_queue: queue.Queue = queue.Queue(-1)
            _global_queue_handler = SafeQueueHandler(log_queue)

            # Task 1: 10 MB limit (maxBytes=10485760), retain 5 backups (backupCount=5)
            import os
            os.makedirs("logs", exist_ok=True)
            file_handler = SafeRotatingFileHandler(
                filename=os.path.join("logs", "aurexis.log"),
                mode='a',
                maxBytes=10485760,
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            
            # Task 2: QueueListener runs entirely on a separate background thread
            _log_queue_listener = logging.handlers.QueueListener(
                log_queue, file_handler, console_handler, respect_handler_level=True
            )
            _log_queue_listener.start()
            
        logger.addHandler(_global_queue_handler)
        logger.propagate = False
    
    return logger

def stop_async_logger() -> None:
    global _log_queue_listener
    with _logger_lock:
        if _log_queue_listener is not None:
            _log_queue_listener.stop()
            _log_queue_listener = None
