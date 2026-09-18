"""Production entry point for the compiled WEAVE CBT ARQ worker"""


from arq.worker import run_worker
from app.workers.worker import WorkerSettings





def main() -> None:
    """Start the Weave CBT ARQ worker"""
    run_worker(WorkerSettings)


if __name__ == "__main__":
    main()
