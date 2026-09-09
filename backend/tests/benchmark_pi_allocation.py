"""Optional synthetic benchmark. Build Rust and set EQM_CORE_BINARY first."""
import json
import statistics
import time

from app.services.pi_allocation_engine import AllocationEngine
from app.services.pi_planner import expand
from tests.test_pi_allocation_engine import full_world


def main():
    context, request = full_world()
    cases = [expand(context["catalog"], {t:q}, set(), cut) for t,q,cut in [(3645,120000,-1),(9832,10000,0),(2867,100,2)]]
    timing = {}
    for mode in ("python", "rust"):
        samples = []
        for _ in range(5):
            start = time.perf_counter()
            with AllocationEngine(request, context, engine=mode) as engine:
                for _ in range(20):
                    for case in cases:
                        engine.allocate(request, context, case)
                assert engine.used == mode, engine.metadata()
            samples.append(time.perf_counter() - start)
        timing[mode] = statistics.median(samples)
    print(json.dumps({"description":"60 allocations, two pilots and eight planet candidates. Includes worker startup and JSON IPC; median of five runs. Synthetic workload, not a general performance guarantee.","seconds":timing,"speedup":timing["python"]/timing["rust"]}, indent=2))


if __name__ == "__main__":
    main()
