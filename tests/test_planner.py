from leskdoo.planner import recommend

def test_low_resources_refuses():
    h={'ram_available_gb':5,'cpu_physical':2,'disks':[],'virtualbox_installed':True}
    assert not recommend(h)['eligible']

def test_healthy_machine():
    h={'ram_available_gb':23,'cpu_physical':8,'disks':[{'mount':'D:/','free_gb':200}],'virtualbox_installed':True}
    r=recommend(h)
    assert r['eligible'] and r['ram_gb']<=12 and r['vcpus']<=4
