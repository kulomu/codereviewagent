from dataclasses import dataclass
from typing import Dict, List, Optional
import aiohttp
import json
import subprocess
from pathlib import Path
import logging
import shutil
from configs import settings
import requests

logger = logging.getLogger(__name__)

@dataclass
class InstallConfig:
    command: str
    args: List[str]
    install_path: str

@dataclass
class MCPInfo:
    name: str
    version: str
    description: str

class MCPInstaller:
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self._config: Dict = {}
        self._load_config()

    def _load_config(self) -> None:
        if self.config_path.exists():
            try:
                self._config = json.load(self.config_path.open('r'))
            except json.JSONDecodeError:
                self._config = {}

    def _save_config(self) -> None:
        with self.config_path.open('w') as f:
            json.dump(self._config, f, indent=2)

    async def install_mcp(self, remote_path: str, install_path: Optional[str] = None, mcp_name: Optional[str] = None) -> None:
        is_local = Path(remote_path).exists()

        try:
            if is_local:
                await self._install_from_local(Path(remote_path), install_path, mcp_name)
            else:
                await self._install_from_remote(remote_path, install_path, mcp_name)

        except Exception as e:
            logger.error(f"安裝 MCP 失敗: {str(e)}")
            raise

    async def _install_from_local(self, local_path: Path, install_path: Optional[str], mcp_name: Optional[str]) -> None:
        if not local_path.exists():
            raise FileNotFoundError(f"指定的本地 MCP 路徑不存在: {local_path}")

        if not mcp_name:
            mcp_name = local_path.name

        if not install_path:
            install_path = str(Path.home() / "mcp_servers")
        target_dir = Path(install_path) / mcp_name
        target_dir.mkdir(parents=True, exist_ok=True)

        if local_path.is_dir():
            for item in local_path.iterdir():
                dst = target_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dst)
        else:
            shutil.copy2(local_path, target_dir / local_path.name)

        mcp_config = await self._get_mcp_config(target_dir)
        self._config[mcp_name] = {
            "command": mcp_config.get("command", "python"),
            "args": mcp_config.get("args", []),
            "install_path": str(target_dir),
            "source": {"type": "local", "path": str(local_path)}
        }
        self._save_config()
        logger.info(f"✅ 成功從本地安裝 MCP {mcp_name}")

    async def _install_from_remote(self, remote_path: str, install_path: Optional[str], mcp_name: Optional[str]) -> None:
        """
        使用 git clone monorepo（https + token），再複製指定資料夾到 mcp_servers，不保留 .git。
        """
        import tempfile

        gitlab_token = settings.GITLAB_TOKEN
        if not gitlab_token:
            raise RuntimeError("安裝失敗：未設置 GITLAB_TOKEN 環境變數，無法執行 git clone")

        repo_url_with_token = f"https://oauth2:{gitlab_token}@github.com/aicr-mcps.git"
        TARGET_BRANCH = "main"

        subfolder = remote_path.strip("/")

        if not install_path:
            install_path = str(Path.home() / "mcp_servers")

        target_dir = Path(install_path)
        target_dir.mkdir(parents=True, exist_ok=True)

        if not mcp_name:
            mcp_name = subfolder

        final_install_path = target_dir / mcp_name

        print(f"🚀 使用 git clone (HTTPS + Token) {repo_url_with_token} 並複製 {subfolder}/ 到暫存目錄")
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_clone_path = Path(tmpdir) / "aicr-mcps"

            subprocess.run(
                ["git", "clone", "--depth", "1", "--branch", TARGET_BRANCH, repo_url_with_token, str(tmp_clone_path)],
                check=True
            )

            source_subfolder = tmp_clone_path / 'mcp_servers' / subfolder
            if not source_subfolder.exists():
                raise FileNotFoundError(f"在 monorepo 中找不到資料夾：{subfolder}")

            if final_install_path.exists():
                shutil.rmtree(final_install_path)

            shutil.copytree(source_subfolder, final_install_path)
            print(f"✅ 成功複製 {subfolder} 到 {final_install_path}")

        mcp_config = await self._get_mcp_config(final_install_path)
        self._config[mcp_name] = {
            "command": mcp_config.get("command", "python"),
            "args": mcp_config.get("args", []),
            "install_path": str(final_install_path),
            "source": {
                "type": "git",
                "repo": "aicr-mcps",
                "subfolder": subfolder
            }
        }
        self._save_config()
        logger.info(f"✅ 成功從 monorepo 安裝 MCP {mcp_name}")

    async def _get_mcp_config(self, install_path: Path) -> Dict:
        try:
            script_path = install_path / "main.py"
            if not script_path.exists():
                raise FileNotFoundError(f"找不到 main.py 腳本：{script_path}")

            print(f"🚀 啟動 MCP 取得 config：{script_path}")

            mcp_name = install_path.name
            project_root = install_path.parent.parent

            result = subprocess.run(
                ["python", "-m", f"mcp_servers.{mcp_name}.main", "--dump-config"],
                cwd=str(project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            if result.returncode != 0:
                raise RuntimeError(
                    f"執行 main.py --dump-config 失敗：{result.stderr.strip()}"
                )

            try:
                config = json.loads(result.stdout.strip())
                transformed_config = {
                    "command": config.get("command", {}).get("run", {}).get("command", "uv"),
                    "args": [
                        "run",
                        "-m",
                        f"mcp_servers.{mcp_name}.main"
                    ]
                }
                return transformed_config

            except json.JSONDecodeError:
                raise RuntimeError(
                    f"config 輸出 JSON 解析錯誤：{result.stdout.strip()}"
                )

        except Exception as e:
            raise RuntimeError(f"取得 config 錯誤：{str(e)} (cwd: {install_path})")

    async def get_local_mcps(self) -> List[str]:
        return list(self._config.keys())

    async def list_remote_mcps(self) -> List[MCPInfo]:
        """
        取得遠端 MCP 列表
        """
        import requests

        GITLAB_API_URL = "https://gitlab.com/api/v4"
        PROJECT_ID = "2255"

        gitlab_token = settings.GITLAB_TOKEN
        if not gitlab_token:
            raise RuntimeError("安裝失敗：未設置 GITLAB_TOKEN 環境變數，無法呼叫 GitLab API")

        headers = {
            "PRIVATE-TOKEN": gitlab_token
        }

        url = f"{GITLAB_API_URL}/projects/{PROJECT_ID}/repository/tree?path=mcp_servers&ref=main"

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error(f"取得 GitLab MCP 列表失敗: {e}")
            data = [{"name": "code_review"}]

        mcps = []
        for item in data:
            if item.get("type") == "tree":
                mcps.append(
                    MCPInfo(
                        name=item.get("name", "-"),
                        version="-",
                        description="-"
                    )
                )
        return mcps


    async def compare_mcps(self) -> Dict[str, str]:
        """
        比對本地 MCP 與遠端 MCP
        回傳 dict: {名稱: 'installed' or 'not_installed'}
        """
        local_mcps = await self.get_local_mcps()
        status = {}
        for name in local_mcps:
            status[name] = "installed"
        return status
