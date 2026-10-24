"""Database persistence tests use temporary SQLite, never production PostgreSQL."""
from datetime import datetime
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session
from leskdoo.db import Base, ManagedVM


def test_schema_and_record_roundtrip(tmp_path):
    engine=create_engine("sqlite:///"+str(tmp_path/"inventory.sqlite"))
    Base.metadata.create_all(engine)
    assert "managed_vms" in inspect(engine).get_table_names()
    with Session(engine) as session:
        record=ManagedVM(uuid="12345678-1234-1234-1234-123456789abc",
                         name="leskdoo-ubuntu",username="aray",ssh_port=2222,
                         stage="registered",notes="teste")
        session.add(record)
        session.commit()
    with Session(engine) as session:
        vm=session.scalar(select(ManagedVM).where(ManagedVM.name=="leskdoo-ubuntu"))
        assert vm.uuid=="12345678-1234-1234-1234-123456789abc"
        assert vm.username=="aray"
        assert vm.ssh_port==2222
        assert isinstance(vm.created_at,datetime)


def test_connect_factory(monkeypatch,tmp_path):
    url="sqlite:///"+str(tmp_path/"vm.sqlite")
    factory=__import__("leskdoo.db",fromlist=["connect"]).connect(url)
    with factory() as session:
        session.add(ManagedVM(uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                              name="test-vm",username="aray"))
        session.commit()
    with factory() as session:
        assert session.query(ManagedVM).count()==1
