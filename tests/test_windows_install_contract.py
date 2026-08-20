from pathlib import Path
import tomllib


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_windows_dependencies_are_platform_scoped() -> None:
    pyproject = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    dependencies = set(pyproject["project"]["dependencies"])
    assert "Pillow; sys_platform == 'win32'" in dependencies
    assert "pystray; sys_platform == 'win32'" in dependencies
    assert "pywin32; sys_platform == 'win32'" in dependencies


def test_windows_source_install_uses_project_venv_and_launcher() -> None:
    install = PROJECT_ROOT / "scripts" / "install-windows.ps1"
    launcher = PROJECT_ROOT / "windows" / "launcher.pyw"
    assert install.is_file()
    assert launcher.is_file()
    script = install.read_text(encoding="utf-8")
    assert ".venv\\Scripts\\python.exe" in script
    assert ".venv\\Scripts\\pythonw.exe" in script
    assert "pip install -e" in script
    assert 'main(["app"])' in launcher.read_text(encoding="utf-8")
