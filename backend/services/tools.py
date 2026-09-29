import json
import os
import shutil
from pathlib import Path


def blender_path():
    candidates = [os.environ.get('FORGE_BLENDER'), shutil.which('blender')]
    if os.name == 'nt':
        import winreg
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(hive, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall') as root:
                    for index in range(winreg.QueryInfoKey(root)[0]):
                        try:
                            with winreg.OpenKey(root, winreg.EnumKey(root, index)) as key:
                                name = winreg.QueryValueEx(key, 'DisplayName')[0]
                                if name.lower() == 'blender':
                                    candidates.append(str(Path(winreg.QueryValueEx(key, 'InstallLocation')[0])/'blender.exe'))
                        except OSError:
                            continue
            except OSError:
                pass
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and Path(candidate).name.lower() in {'blender', 'blender.exe'}:
            return str(Path(candidate).resolve())
    return None


def unreal_installations():
    registry = Path(os.environ.get('PROGRAMDATA', 'C:/ProgramData'))/'Epic/UnrealEngineLauncher/LauncherInstalled.dat'
    results = {}
    try:
        for entry in json.loads(registry.read_text()).get('InstallationList', []):
            if entry.get('NamespaceId') != 'ue':
                continue
            root = Path(entry['InstallLocation'])
            version_path = root/'Engine/Build/Build.version'
            executable = root/'Engine/Binaries/Win64/UnrealEditor-Cmd.exe'
            if not executable.exists():
                executable = root/'Engine/Binaries/Win64/UE4Editor-Cmd.exe'
            if version_path.is_file() and executable.is_file():
                version = json.loads(version_path.read_text())
                results[str(root)] = {'path': str(root), 'version': '.'.join(str(version[k]) for k in ('MajorVersion', 'MinorVersion', 'PatchVersion')), 'editor': str(executable)}
    except (OSError, ValueError, KeyError):
        pass
    return list(results.values())
