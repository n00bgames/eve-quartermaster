from __future__ import annotations

import copy
import os
from pathlib import Path
import shutil
import subprocess
import time

import pytest

from app.services.pi_allocation_engine import AllocationEngine, equivalent
from app.services.pi_planner import allocate, evaluate, expand
from tests.test_pi_planner import context, market, request


def rust_binary():
    configured = os.environ.get("EQM_CORE_BINARY", "eqm-core")
    path = shutil.which(configured) or (configured if Path(configured).is_file() else None)
    if not path:
        pytest.skip("Build eqm-core and set EQM_CORE_BINARY to run native allocation parity")
    return path


def full_world():
    c, r = context(), request(search_seconds=30)
    c["pilots"].append({**copy.deepcopy(c["pilots"][0]), "character_id":2, "name":"Second", "ccu":4, "ic":3})
    planets=[]
    for i, kind in enumerate(["Barren","Gas","Ice","Lava","Oceanic","Plasma","Storm","Temperate"]):
        planets.append({"key":str(i),"name":kind,"planet_type":kind,"security":.7 if i%2 else 0,"customs_percent":5+i,"npc_tax_percent":10,"yields":[{"type_id":t,"units_per_head_hour":2500+i*600,"source":"scan"} for t,v in c["catalog"].items() if kind in v["planet_types"]]})
    r=request(planets=planets,pilots=[{"character_id":p["character_id"],"planet_keys":[str(i) for i in range(8)]} for p in c["pilots"]],search_seconds=30)
    return c,r


def test_every_recipe_matches_rust_and_preserves_validation_and_prices():
    c,r=full_world()
    with AllocationEngine(r,c,engine="rust",binary=rust_binary()) as engine:
        assert engine.used=="rust"
        for t,item in c["catalog"].items():
            if not item["recipe"]:continue
            for scale in (1,100):
                engine.deadline=time.monotonic()+30
                targets={t:item["recipe"]["output"]["quantity"]*scale}
                cut=item["tier"]-1
                reference=evaluate(r,c,market(),targets,cut)
                native=evaluate(r,c,market(),targets,cut,allocator=engine.allocate)
                assert equivalent(reference,native), (item["name"],scale)
                assert native["feasible"],native["reason"]
                assert native["validation_errors"]==[]
        assert engine.used=="rust"  # A fallback cannot make parity pass silently.


def test_extraction_mixes_and_capacity_boundaries_match():
    c,r=full_world()
    with AllocationEngine(r,c,engine="rust",binary=rust_binary()) as engine:
        for t,item in c["catalog"].items():
            if item["tier"]!=1:continue
            for q in (20,20000,120000,10000000):
                engine.deadline=time.monotonic()+30
                expanded=expand(c["catalog"],{t:q},set(),-1)
                assert equivalent(allocate(r,c,expanded),engine.allocate(r,c,expanded)),(t,q)
        for targets,cut in [({3645:21,9832:5},1),({2867:10},-1),({9832:10000},0)]:
            engine.deadline=time.monotonic()+30
            expanded=expand(c["catalog"],targets,set(),cut)
            assert equivalent(allocate(r,c,expanded),engine.allocate(r,c,expanded))
        assert engine.used=="rust"


@pytest.mark.parametrize("level",range(6))
def test_low_skills_replacement_and_cadence_native_parity(level):
    c,r=context(),request(search_seconds=30)
    c["pilots"][0].update(ccu=level,ic=level,colonies=[{"id":1,"planet_id":100,"upgrade_level":2}])
    r.pilots[0].release_colony_ids=[1]
    r.planets[0].planet_id=100
    r.schedule.visits_per_week=1+level
    r.schedule.program_hours=48
    r.schedule.link_length_km=500
    expanded=expand(c["catalog"],{3645:10000},set(),-1)
    with AllocationEngine(r,c,engine="shadow",binary=rust_binary()) as engine:
        engine.allocate(r,c,expanded)
        assert engine.used=="shadow"


def test_missing_binary_fallback_and_python_mode():
    c,r=context(),request()
    expanded=expand(c["catalog"],{3645:20},set(),-1)
    for mode in ("rust","python"):
        with AllocationEngine(r,c,engine=mode,binary="/missing/eqm-core") as engine:
            assert engine.allocate(r,c,expanded)==allocate(r,c,expanded)
            assert engine.used==("python-fallback" if mode=="rust" else "python")


def test_worker_rejects_bad_contract_without_panic():
    binary=rust_binary()
    response=subprocess.run([binary,"pi-allocation-worker"],input='{"schema_version":"unknown"}\n',text=True,capture_output=True,timeout=5,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    assert response.returncode!=0
    assert "panic" not in response.stderr.lower()


def test_worker_death_falls_back_and_shutdown_reaps_process():
    c,r=context(),request()
    expanded=expand(c["catalog"],{3645:20000},set(),-1)
    with AllocationEngine(r,c,engine="rust",binary=rust_binary()) as engine:
        process=engine.process
        process.kill();process.wait(timeout=2)
        assert equivalent(engine.allocate(r,c,expanded),allocate(r,c,expanded))
        assert engine.used=="python-fallback"
    assert process.poll() is not None


def test_water_capacity_matches_direct_arithmetic():
    c,r=context(),request()
    expanded=expand(c["catalog"],{3645:20000},set(),-1)
    with AllocationEngine(r,c,engine="rust",binary=rust_binary()) as engine:
        colonies,_=engine.allocate(r,c,expanded)
        colony=colonies[0]
        assert colony["processors"]==3 and colony["heads"]==2
        assert colony["cpu"]==3600+3*200+400+2*110+4*(15+.2*100)
        assert colony["power"]==700+3*800+2600+2*550+4*(10+.15*100)
