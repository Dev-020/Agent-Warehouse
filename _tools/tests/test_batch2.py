"""Tests for Phase 2 Batch 2 commands."""
from pathlib import Path

def test_template(wh):
    wh.publish("template/t", "1.0.0", settings={"name": "your name"}, body="Hello {{name}}!\n")
    p = wh.project("alpha", "items: []")
    
    code, out = wh.run("template", "template/t", str(p / "hello.md"), "--set", "name=World")
    assert code == 0
    text = (p / "hello.md").read_text()
    assert "Hello World!" in text
    assert "from warehouse template template/t v1.0.0" in text

    # test with explicit version
    code, out = wh.run("template", "template/t@1.0.0", str(p / "hello2.md"), "--set", "name=Explicit")
    assert code == 0
    assert "Hello Explicit!" in (p / "hello2.md").read_text()

def test_bootstrap_codebase(wh):
    p = wh.project("alpha", "")
    (p / "package.json").touch()
    
    # use wh.publish to properly format items and changelogs
    wh.publish("tool/t", "1.0.0", body="Body", tool_fields={"applies-to": ["codebase"]})
    
    # but publish hardcodes applies-to: [vault, codebase]. Let's just override it via text replacement and commit!
    t_path = wh.root / "tools" / "t" / "TOOL.md"
    t_path.write_text(t_path.read_text().replace("applies-to: [vault, codebase]", "applies-to: [codebase]"))
    wh.commit("modify tool/t")
    import subprocess
    subprocess.run(["git", "-C", str(wh.root), "tag", "-f", "-a", "tool/t@1.0.0", "-m", "1.0.0"], check=True)
    
    wh.publish("protocol/p", "1.0.0", body="Body")
    p_path = wh.root / "protocols" / "p.md"
    p_path.write_text(p_path.read_text().replace("applies-to: [vault, codebase]", "applies-to: [vault]"))
    wh.commit("modify protocol/p")
    subprocess.run(["git", "-C", str(wh.root), "tag", "-f", "-a", "protocol/p@1.0.0", "-m", "1.0.0"], check=True)
    
    code, out = wh.run("bootstrap", "--profile", "all", project=p)
    assert code == 0
    assert "auto_sync: true" in out
    assert "target: warehouse/" in out
    assert "tool/t@1" in out
    assert "protocol/p" not in out
    
    (p / ".warehouse.yml").unlink()
    code, out = wh.run("bootstrap", "--profile", "all", "--write", project=p)
    assert code == 0
    assert (p / ".warehouse.yml").exists()
    assert "tool/t@1" in (p / ".warehouse.yml").read_text()
    assert "target: warehouse/" in (p / ".warehouse.yml").read_text()

def test_detach(wh):
    wh.publish("skill/s", "1.0.0", body="Content")
    p = wh.project("alpha", "items:\n  - skill/s@1\n")
    wh.run("sync")
    assert (p / "warehouse" / "skills" / "s" / "SKILL.md").exists()
    
    code, out = wh.run("detach", "skill/s", project=p)
    assert code == 0
    assert "move out of warehouse" in out
    text = (p / "warehouse" / "skills" / "s" / "SKILL.md").read_text()
    assert "Content" in text
    assert "> [!info] Warehouse item" not in text
    assert "skill/s@1" not in (p / ".warehouse.yml").read_text()

def test_discard(wh):
    wh.publish("skill/s", "1.0.0", body="Content")
    p = wh.project("alpha", "items:\n  - skill/s@1\n")
    wh.run("sync")
    
    (p / "warehouse" / "skills" / "s" / "SKILL.md").write_text("Drifted Content")
    code, out = wh.run("discard", "skill/s", project=p)
    assert code == 10
    assert "Drifted Content" in out
    
    code, out = wh.run("discard", "skill/s", "--yes", project=p)
    assert code == 0
    text = (p / "warehouse" / "skills" / "s" / "SKILL.md").read_text()
    assert "Content" in text
    assert "Drifted Content" not in text

def test_promote(wh):
    wh.publish("skill/s", "1.0.0", body="Content")
    p = wh.project("alpha", "items:\n  - skill/s@1\n")
    wh.run("sync")
    
    (p / "warehouse" / "skills" / "s" / "SKILL.md").write_text("Drifted Content")
    code, out = wh.run("promote", "skill/s", project=p)
    assert code == 0
    assert "Drifted Content" in (wh.root / "skills" / "s" / "SKILL.md").read_text()
    assert "- Promoted from " in (wh.root / "skills" / "s" / "CHANGELOG.md").read_text()
def test_promote_document(wh):
    wh.publish('protocol/p', '1.0.0', body='Content')
    p = wh.project('alpha', 'items:\n  - protocol/p@1\n')
    wh.run('sync')
    orig = (p / 'warehouse' / 'p.md').read_text()
    (p / 'warehouse' / 'p.md').write_text(orig.replace('Content', 'Drifted Content'))
    code, out = wh.run('promote', 'protocol/p', project=p)
    assert code == 0

def test_promote_include_new(wh):
    wh.publish("skill/s", "1.0.0", body="Content")
    p = wh.project("alpha", "items:\n  - skill/s@1\n")
    wh.run("sync")
    
    extra = p / "warehouse" / "skills" / "s" / "extra.txt"
    extra.write_text("extra file")
    
    # without --include-new, untracked file is ignored
    code, out = wh.run("promote", "skill/s", project=p)
    assert code == 0
    assert not (wh.root / "skills" / "s" / "extra.txt").exists()
    
    # with --include-new, untracked file is copied to master
    code, out = wh.run("promote", "skill/s", "--include-new", project=p)
    assert code == 0
    assert (wh.root / "skills" / "s" / "extra.txt").exists()
    assert (wh.root / "skills" / "s" / "extra.txt").read_text() == "extra file"

def test_promote_deleted_file(wh):
    wh.publish("skill/s", "1.0.0", body="Content")
    p = wh.project("alpha", "items:\n  - skill/s@1\n")
    wh.run("sync")
    
    # delete skill file in project
    skill_file = p / "warehouse" / "skills" / "s" / "SKILL.md"
    skill_file.unlink()
    
    code, out = wh.run("promote", "skill/s", project=p)
    assert code == 0
    # master file must still exist!
    assert (wh.root / "skills" / "s" / "SKILL.md").exists()
