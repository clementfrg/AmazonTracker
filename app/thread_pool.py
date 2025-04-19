from concurrent.futures import ThreadPoolExecutor
import os

# Taille du pool configurable par variable d'environnement ou valeur par défaut
DEFAULT_THREAD_POOL_SIZE = 30

# Instance unique du thread pool global
global_executor = None

def init_thread_pool(max_workers=DEFAULT_THREAD_POOL_SIZE):
    global global_executor
    if global_executor is None:
        global_executor = ThreadPoolExecutor(max_workers=max_workers)

def submit_task(fn, *args, **kwargs):
    if global_executor is None:
        raise RuntimeError("Thread pool not initialized. Call init_thread_pool() first.")
    return global_executor.submit(fn, *args, **kwargs)

def shutdown_thread_pool():
    global global_executor
    if global_executor:
        global_executor.shutdown(wait=True)
        global_executor = None
